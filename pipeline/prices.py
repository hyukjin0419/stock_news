"""
종목 시세 — 최근 종가 + 전일 대비 변동률.
  KR → FinanceDataReader, US → yfinance.
주의: 새벽 6시 기준 국내장은 미개장이라 '최신 종가'는 전일 종가다(직전 2거래일 비교).
"""
from datetime import datetime, timedelta


def get_price(stock: dict) -> dict | None:
    """{price, change_pct, currency} 또는 실패 시 None."""
    try:
        if stock["market"] == "KR":
            last, prev = _kr_closes(stock["ticker"])
            currency = "KRW"
        elif stock["market"] == "US":
            last, prev = _us_closes(stock["ticker"])
            currency = "USD"
        else:
            return None
    except Exception as e:
        print(f"  ⚠️ 시세 실패 ({stock['name']}): {e}")
        return None

    if not last or not prev:
        return None
    return {
        "price": last,
        "change_pct": (last - prev) / prev * 100,
        "currency": currency,
    }


def _kr_closes(ticker: str) -> tuple[float, float]:
    import FinanceDataReader as fdr

    start = (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d")
    df = fdr.DataReader(ticker, start)
    closes = df["Close"].tolist()
    return closes[-1], closes[-2]


def _us_closes(ticker: str) -> tuple[float, float]:
    import yfinance as yf

    hist = yf.Ticker(ticker).history(period="7d")
    closes = hist["Close"].tolist()
    return closes[-1], closes[-2]


def format_amount(p: dict | None) -> str:
    """종가: '₩322,500' / '$170.50'."""
    if not p:
        return "-"
    sym = "₩" if p["currency"] == "KRW" else "$"
    amt = f"{p['price']:,.0f}" if p["currency"] == "KRW" else f"{p['price']:,.2f}"
    return f"{sym}{amt}"


def format_change(p: dict | None) -> str:
    """전일대비: '▲7.86%' / '▼0.80%'."""
    if not p:
        return "-"
    chg = p["change_pct"]
    arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "−")
    return f"{arrow}{abs(chg):.2f}%"
