"""회원별 시세+뉴스 → HTML 이메일 본문."""
from datetime import datetime
from html import escape

from prices import format_amount, format_change


def _esc(s) -> str:
    """HTML 본문/속성 삽입용 이스케이프 (뉴스 제목·요약·LLM 출력 등 외부 텍스트)."""
    return escape(str(s or ""), quote=True)


def _safe_url(url: str) -> str:
    """http(s) 링크만 허용하고 이스케이프. 그 외 스킴(javascript: 등)은 빈 값."""
    url = str(url or "")
    return _esc(url) if url.startswith(("http://", "https://")) else ""


def render_email(price_rows: list[dict], stock_sections: list[dict]) -> str:
    """
    price_rows:     [{name, ticker, market, price: dict|None}, ...]  (전 종목)
    stock_sections: [{name, ticker, market, items: [NewsItem],
                      digest: dict|None}, ...]  (전 종목 — 뉴스 없으면 items 빈 배열)
    """
    price_table = _price_table(price_rows)

    blocks = []
    for sec in stock_sections:
        tag_color = "#d33" if sec["market"] == "KR" else "#2563eb"
        header = f"""<h2 style="font-size:18px;margin:0 0 4px;">
                {_esc(sec['name'])}
                <span style="font-size:12px;color:#888;">{_esc(sec['ticker'])}</span>
                <span style="font-size:11px;color:#fff;background:{tag_color};
                       border-radius:4px;padding:1px 6px;">{_esc(sec['market'])}</span>
              </h2>"""
        if sec["items"]:
            body = _digest_block(sec.get("digest")) + "".join(
                _article_html(i) for i in sec["items"]
            )
        else:
            body = (
                '<p style="color:#999;font-size:13px;margin:6px 0 0;">'
                "오늘 새 뉴스가 없어요.</p>"
            )
        blocks.append(f'<div style="margin:28px 0;">{header}{body}</div>')

    today = datetime.now().strftime("%Y-%m-%d")
    return f"""
    <div style="font-family:-apple-system,system-ui,sans-serif;max-width:640px;
                margin:0 auto;color:#1a1a1a;">
      <h1 style="font-size:22px;">📈 FIRSTWAVE</h1>
      <p style="color:#888;font-size:13px;">관심종목 브리핑 · {today}</p>
      {price_table}
      {''.join(blocks)}
      <hr style="border:none;border-top:1px solid #eee;margin:32px 0;" />
      <p style="color:#aaa;font-size:12px;">
        시세·뉴스 수집·요약 자동화. 투자 판단은 본인의 몫입니다.
      </p>
    </div>"""


def _price_table(rows: list[dict]) -> str:
    if not rows:
        return ""
    th = (
        'style="padding:6px 0;font-size:12px;color:#999;font-weight:600;'
        'border-bottom:1px solid #eee;"'
    )
    header = f"""<tr>
        <td {th}>종목</td>
        <td {th} align="right">종가</td>
        <td {th} align="right">전일대비</td>
      </tr>"""
    trs = [header]
    for r in rows:
        p = r.get("price")
        chg = p["change_pct"] if p else 0
        color = "#16a34a" if chg > 0 else ("#dc2626" if chg < 0 else "#888")
        trs.append(
            f"""<tr>
              <td style="padding:8px 0;font-size:14px;">{_esc(r['name'])}
                <span style="color:#aaa;font-size:12px;">{_esc(r['ticker'])}</span></td>
              <td style="padding:8px 0;font-size:14px;text-align:right;font-weight:600;">
                {format_amount(p)}</td>
              <td style="padding:8px 0;font-size:14px;text-align:right;
                  color:{color};font-weight:600;">{format_change(p)}</td>
            </tr>"""
        )
    return f"""
    <table style="width:100%;border-collapse:collapse;margin:16px 0 8px;">
      {''.join(trs)}
    </table>"""


def _digest_block(digest: dict | None) -> str:
    if not digest:
        return ""
    parts = [
        ("호재", "#16a34a", "📈"),
        ("악재", "#dc2626", "📉"),
        ("액션", "#2563eb", "🎯"),
    ]
    cards = []
    for key, color, icon in parts:
        items = digest.get(key) or []
        if not items:
            continue
        lis = "".join(
            f'<li style="margin:3px 0;">{_esc(x)}</li>' for x in items
        )
        label = "주목 포인트" if key == "액션" else key
        cards.append(
            f"""<div style="margin:8px 0;">
              <div style="font-size:13px;font-weight:700;color:{color};">
                {icon} {label}</div>
              <ul style="margin:4px 0 0;padding-left:18px;font-size:13px;
                  color:#333;line-height:1.5;">{lis}</ul>
            </div>"""
        )
    if not cards:
        return ""
    return f"""
    <div style="background:#f8f9fa;border-radius:10px;padding:12px 16px;margin:6px 0 10px;">
      {''.join(cards)}
    </div>"""


def _article_html(item) -> str:
    date = item.published_at.strftime("%m/%d %H:%M")
    return f"""
    <div style="padding:12px 0;border-bottom:1px solid #eee;">
      <a href="{_safe_url(item.url)}" style="font-size:15px;font-weight:600;
         color:#111;text-decoration:none;">{_esc(item.title)}</a>
      <div style="font-size:12px;color:#999;margin:2px 0 6px;">
        {_esc(item.source)} · {date}</div>
      <div style="font-size:14px;color:#333;line-height:1.5;">{_esc(item.summary)}</div>
    </div>"""
