"""회원별 시세+뉴스 → HTML 이메일 본문."""
from datetime import datetime

from prices import format_amount, format_change


def render_email(
    price_rows: list[dict], digest: dict | None, stock_sections: list[dict]
) -> str:
    """
    price_rows:     [{name, ticker, market, price: dict|None}, ...]  (전 종목)
    digest:         {"호재":[...], "악재":[...], "액션":[...]} 또는 None
    stock_sections: [{name, ticker, market, items: [NewsItem]}, ...] (새 뉴스 있는 종목)
    """
    price_table = _price_table(price_rows)
    digest_html = _digest_block(digest)

    blocks = []
    for sec in stock_sections:
        tag_color = "#d33" if sec["market"] == "KR" else "#2563eb"
        articles = "".join(_article_html(i) for i in sec["items"])
        blocks.append(
            f"""
            <div style="margin:28px 0;">
              <h2 style="font-size:18px;margin:0 0 4px;">
                {sec['name']}
                <span style="font-size:12px;color:#888;">{sec['ticker']}</span>
                <span style="font-size:11px;color:#fff;background:{tag_color};
                       border-radius:4px;padding:1px 6px;">{sec['market']}</span>
              </h2>
              {articles}
            </div>"""
        )

    today = datetime.now().strftime("%Y-%m-%d")
    news_html = "".join(blocks) if blocks else (
        '<p style="color:#888;font-size:14px;margin:24px 0;">오늘 새로운 뉴스는 없어요.</p>'
    )
    return f"""
    <div style="font-family:-apple-system,system-ui,sans-serif;max-width:640px;
                margin:0 auto;color:#1a1a1a;">
      <h1 style="font-size:22px;">📈 관심종목 브리핑</h1>
      <p style="color:#888;font-size:13px;">{today}</p>
      {price_table}
      {digest_html}
      {news_html}
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
              <td style="padding:8px 0;font-size:14px;">{r['name']}
                <span style="color:#aaa;font-size:12px;">{r['ticker']}</span></td>
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
            f'<li style="margin:3px 0;">{x}</li>' for x in items
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
    <div style="background:#f8f9fa;border-radius:10px;padding:14px 16px;margin:8px 0 4px;">
      <div style="font-size:14px;font-weight:700;margin-bottom:4px;">🧭 오늘의 요약</div>
      {''.join(cards)}
    </div>"""


def _article_html(item) -> str:
    date = item.published_at.strftime("%m/%d %H:%M")
    return f"""
    <div style="padding:12px 0;border-bottom:1px solid #eee;">
      <a href="{item.url}" style="font-size:15px;font-weight:600;
         color:#111;text-decoration:none;">{item.title}</a>
      <div style="font-size:12px;color:#999;margin:2px 0 6px;">
        {item.source} · {date}</div>
      <div style="font-size:14px;color:#333;line-height:1.5;">{item.summary}</div>
    </div>"""
