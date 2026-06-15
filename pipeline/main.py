"""
파이프라인 진입점.
  1) 전 회원 watchlist 로드
  2) 고유 종목별로 1회만 뉴스 수집 + 본문추출 + 요약
  3) 회원별로 조립(이미 보낸 기사 제외) → Gmail 발송 → sent_news 기록
"""
from datetime import datetime

from fetchers import fetch_news
from mailer import send_email
from prices import get_price
from render import render_email
from repo import get_sent_urls, load_members, record_sent
from summarizer import analyze, make_digest


def run() -> None:
    members = load_members()
    if not members:
        print("구독 중인 회원이 없습니다.")
        return
    print(f"회원 {len(members)}명, 종목 수집 시작")

    # 2) 고유 종목 1회 수집(시세 + 뉴스) — key=(market, ticker)
    cache: dict[tuple[str, str], dict] = {}
    for m in members:
        for s in m["stocks"]:
            cache.setdefault((s["market"], s["ticker"]), {"stock": s})

    for key, entry in cache.items():
        s = entry["stock"]
        print(f"  📰 {s['name']} ({s['ticker']})")
        entry["price"] = get_price(s)
        kept = []
        for it in fetch_news(s):
            if analyze(it, s["name"]):
                kept.append(it)
            else:
                print(f"     ↳ 무관 제외: {it.title[:40]}")
        entry["items"] = kept

    # 3) 회원별 조립 + 발송 (시세는 항상, 뉴스는 새 기사 있을 때)
    sent_cnt = 0
    for m in members:
        sent_urls = get_sent_urls(m["user_id"])
        price_rows, sections, new_urls = [], [], []
        for s in m["stocks"]:
            entry = cache[(s["market"], s["ticker"])]
            price_rows.append({**s, "price": entry.get("price")})
            fresh = [i for i in (entry.get("items") or []) if i.url not in sent_urls]
            digest = make_digest(fresh, s["name"]) if fresh else None
            sections.append({**s, "items": fresh, "digest": digest})
            new_urls += [i.url for i in fresh]

        subject = f"📈 [{datetime.now():%Y-%m-%d}] 관심종목 브리핑"
        if send_email(m["email"], subject, render_email(price_rows, sections)):
            record_sent(m["user_id"], new_urls)
            sent_cnt += 1
            print(f"  ✅ {m['email']} — 시세 {len(price_rows)} / 새뉴스 {len(new_urls)}")

    print(f"완료 — {sent_cnt}명 발송")


if __name__ == "__main__":
    run()
