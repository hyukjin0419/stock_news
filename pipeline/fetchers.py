"""
종목 → 뉴스 수집. 시장(market)에 따라 fetcher를 디스패치하고,
모든 결과를 NewsItem으로 정규화한다. 본문은 trafilatura로 추출.

  market=KR → 네이버 뉴스 검색 API (회사명 query)
  market=US → Finnhub company-news (ticker)
"""
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests
import trafilatura
from dotenv import load_dotenv

load_dotenv()

DAYS_BACK = 2  # 어제~오늘만
MAX_PER_STOCK = 5  # 종목당 기사 수 상한
MIN_BODY_LEN = 200

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"
SKIP_DOMAINS = ("youtube.com", "twitter.com", "x.com")


@dataclass
class NewsItem:
    title: str
    url: str
    source: str
    published_at: datetime
    api_summary: str = ""
    body: str = ""
    summary: str = field(default="")  # LLM 요약 (summarizer가 채움)


def _cutoff() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).replace("&quot;", '"').replace("&amp;", "&")


# 종목명에서 떼어낼 흔한 접미사 (관련성 토큰 추출용)
_NAME_SUFFIX = re.compile(
    r"\b(corp(oration)?|inc|incorporated|ltd|limited|co|company|group|holdings?|plc|sa|ag|nv)\b\.?",
    re.I,
)


def _relevance_tokens(stock: dict) -> list[str]:
    """기사 관련성 판정용 토큰: 핵심 종목명 + 티커."""
    name = _NAME_SUFFIX.sub("", stock["name"]).strip(" .,")
    tokens = {name.lower(), stock["ticker"].lower()}
    return [t for t in tokens if len(t) >= 2]


def _mentions(item: "NewsItem", tokens: list[str]) -> bool:
    """제목+API요약에 종목 토큰이 하나라도 등장하는지 (휴리스틱 1단계)."""
    text = f"{item.title} {item.api_summary}".lower()
    return any(t in text for t in tokens)


def fetch_news(stock: dict) -> list[NewsItem]:
    """{ticker, market, name} → 정규화된 NewsItem 목록 (본문 포함)."""
    market = stock["market"]
    if market == "KR":
        items = _fetch_naver(stock["name"])
    elif market == "US":
        items = _fetch_finnhub(stock["ticker"])
    else:
        return []

    items = [i for i in items if i.published_at >= _cutoff()]

    # 1단계 휴리스틱: 종목명/티커 언급 없는 기사 제거 (본문 추출 전)
    tokens = _relevance_tokens(stock)
    items = [i for i in items if _mentions(i, tokens)]

    items.sort(key=lambda i: i.published_at, reverse=True)
    items = items[:MAX_PER_STOCK]

    for item in items:
        item.body = _extract_body(item.url) or item.api_summary
    return [i for i in items if i.body]


# ---------- 국내: 네이버 ----------
def _fetch_naver(query: str) -> list[NewsItem]:
    try:
        res = requests.get(
            "https://openapi.naver.com/v1/search/news.json",
            headers={
                "X-Naver-Client-Id": os.environ["NAVER_CLIENT_ID"],
                "X-Naver-Client-Secret": os.environ["NAVER_CLIENT_SECRET"],
            },
            params={"query": query, "display": 20, "sort": "date"},
            timeout=10,
        )
        res.raise_for_status()
    except Exception as e:
        print(f"  ⚠️ 네이버 수집 실패 ({query}): {e}")
        return []

    out = []
    for it in res.json().get("items", []):
        try:
            pub = parsedate_to_datetime(it["pubDate"])
        except Exception:
            continue
        out.append(
            NewsItem(
                title=_strip_tags(it["title"]),
                url=it.get("originallink") or it["link"],
                source="네이버뉴스",
                published_at=pub,
                api_summary=_strip_tags(it.get("description", "")),
            )
        )
    return out


# ---------- 해외: Finnhub ----------
def _fetch_finnhub(ticker: str) -> list[NewsItem]:
    today = datetime.now(timezone.utc).date()
    frm = today - timedelta(days=DAYS_BACK)
    try:
        res = requests.get(
            "https://finnhub.io/api/v1/company-news",
            params={
                "symbol": ticker,
                "from": frm.isoformat(),
                "to": today.isoformat(),
                "token": os.environ["FINNHUB_API_KEY"],
            },
            timeout=10,
        )
        res.raise_for_status()
    except Exception as e:
        print(f"  ⚠️ Finnhub 수집 실패 ({ticker}): {e}")
        return []

    out = []
    for it in res.json():
        url = it.get("url")
        if not url:
            continue
        out.append(
            NewsItem(
                title=it.get("headline", ""),
                url=url,
                source=it.get("source", "Finnhub"),
                published_at=datetime.fromtimestamp(it["datetime"], tz=timezone.utc),
                api_summary=it.get("summary", ""),
            )
        )
    return out


# ---------- 본문 추출 ----------
def _extract_body(url: str) -> str:
    if any(d in url for d in SKIP_DOMAINS):
        return ""
    try:
        downloaded = trafilatura.fetch_url(url)
        text = trafilatura.extract(downloaded) or ""
        return text if len(text) >= MIN_BODY_LEN else ""
    except Exception:
        return ""
