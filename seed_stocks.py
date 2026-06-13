"""
seed_stocks.py — 종목 마스터(stock 테이블) 1회 시드.

KRX(KOSPI/KOSDAQ) 전체 + 미국(NASDAQ/NYSE)을 FinanceDataReader로 긁어
Supabase stock 테이블에 upsert 합니다. 키 없이 동작(시세 사이트 스크랩).

실행: python seed_stocks.py
"""
import os

import FinanceDataReader as fdr
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"],  # RLS 우회
)

BATCH = 500

# 미국 주요 ETF (무료 통합 리스트가 없어 큐레이션)
US_ETFS = {
    "SPY": "SPDR S&P 500 ETF", "VOO": "Vanguard S&P 500 ETF",
    "IVV": "iShares Core S&P 500 ETF", "QQQ": "Invesco QQQ Trust",
    "VTI": "Vanguard Total Stock Market ETF", "DIA": "SPDR Dow Jones ETF",
    "IWM": "iShares Russell 2000 ETF", "VEA": "Vanguard Developed Markets ETF",
    "VWO": "Vanguard Emerging Markets ETF", "EEM": "iShares MSCI Emerging Markets ETF",
    "EFA": "iShares MSCI EAFE ETF", "AGG": "iShares Core US Aggregate Bond ETF",
    "BND": "Vanguard Total Bond Market ETF", "TLT": "iShares 20+ Year Treasury ETF",
    "LQD": "iShares Investment Grade Bond ETF", "HYG": "iShares High Yield Bond ETF",
    "GLD": "SPDR Gold Shares", "SLV": "iShares Silver Trust",
    "USO": "United States Oil Fund", "ARKK": "ARK Innovation ETF",
    "SOXX": "iShares Semiconductor ETF", "SMH": "VanEck Semiconductor ETF",
    "XLK": "Technology Select Sector SPDR", "XLF": "Financial Select Sector SPDR",
    "XLE": "Energy Select Sector SPDR", "XLV": "Health Care Select Sector SPDR",
    "SCHD": "Schwab US Dividend Equity ETF", "JEPI": "JPMorgan Equity Premium Income ETF",
    "VIG": "Vanguard Dividend Appreciation ETF", "VYM": "Vanguard High Dividend Yield ETF",
}


def collect() -> list[dict]:
    """(ticker, market, name) 목록 수집."""
    rows: list[dict] = []

    # 국내: KRX 전체 (KOSPI+KOSDAQ)
    kr = fdr.StockListing("KRX")  # Code, Name 컬럼
    for _, r in kr.iterrows():
        code, name = r.get("Code"), r.get("Name")
        if code and name:
            rows.append({"ticker": str(code), "market": "KR", "name": str(name)})

    # 국내 ETF
    kr_etf = fdr.StockListing("ETF/KR")  # Symbol, Name 컬럼
    for _, r in kr_etf.iterrows():
        sym, name = r.get("Symbol"), r.get("Name")
        if sym and name:
            rows.append({"ticker": str(sym), "market": "KR", "name": str(name)})

    # 해외: NASDAQ + NYSE
    for exch in ("NASDAQ", "NYSE"):
        us = fdr.StockListing(exch)  # Symbol, Name 컬럼
        for _, r in us.iterrows():
            sym, name = r.get("Symbol"), r.get("Name")
            if sym and name:
                rows.append({"ticker": str(sym), "market": "US", "name": str(name)})

    # 해외 ETF (큐레이션)
    for sym, name in US_ETFS.items():
        rows.append({"ticker": sym, "market": "US", "name": name})

    # (ticker, market) 중복 제거
    seen, unique = set(), []
    for row in rows:
        key = (row["ticker"], row["market"])
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


def main() -> None:
    rows = collect()
    print(f"수집: {len(rows)}개 종목 → upsert 시작")
    for i in range(0, len(rows), BATCH):
        chunk = rows[i : i + BATCH]
        supabase.table("stock").upsert(
            chunk, on_conflict="ticker,market"
        ).execute()
        print(f"  {min(i + BATCH, len(rows))}/{len(rows)}")
    print("완료 ✅")


if __name__ == "__main__":
    main()
