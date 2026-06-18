"""Supabase 데이터 접근 — service_role 키로 RLS 우회(전 회원 조회)."""
import os

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

_sb = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"],
)

FREE_LIMIT = 3  # 무료 회원이 받아볼 수 있는 종목 수 상한
UNLIMITED_PLANS = {"free_legacy", "paid"}  # 무제한 등급


def _plans() -> dict[str, str]:
    """user_id → plan. subscriber 행이 없는 회원은 호출부에서 'free'로 간주."""
    rows = _sb.table("subscriber").select("user_id, plan").execute().data
    return {r["user_id"]: r["plan"] for r in rows}


def load_members() -> list[dict]:
    """
    전 회원의 watchlist를 회원 단위로 묶어 반환.
    [{user_id, email, stocks: [{ticker, market, name}, ...]}, ...]
    무료 회원은 먼저 추가한 종목 FREE_LIMIT개까지만 포함한다.
    """
    rows = (
        _sb.table("watchlist")
        .select("user_id, created_at, stock(ticker, market, name)")
        .order("created_at")  # 오래된 종목 우선 → 무료 컷 시 먼저 담은 3개 유지
        .execute()
        .data
    )

    plans = _plans()

    by_user: dict[str, list[dict]] = {}
    for r in rows:
        by_user.setdefault(r["user_id"], []).append(r["stock"])

    members = []
    for user_id, stocks in by_user.items():
        # 무료 회원(행 없음 또는 plan='free')은 종목 3개로 제한, 유료/기존회원은 무제한
        if plans.get(user_id) not in UNLIMITED_PLANS:
            stocks = stocks[:FREE_LIMIT]
        email = _email_of(user_id)
        if email:
            members.append({"user_id": user_id, "email": email, "stocks": stocks})
    return members


def _email_of(user_id: str) -> str | None:
    """auth.users에서 이메일 조회 (admin API)."""
    try:
        res = _sb.auth.admin.get_user_by_id(user_id)
        return res.user.email
    except Exception as e:
        print(f"  ⚠️ 이메일 조회 실패 ({user_id}): {e}")
        return None


def get_sent_urls(user_id: str) -> set[str]:
    rows = (
        _sb.table("sent_news").select("url").eq("user_id", user_id).execute().data
    )
    return {r["url"] for r in rows}


def record_sent(user_id: str, urls: list[str]) -> None:
    if not urls:
        return
    # 같은 URL이 여러 종목에 잡혀 중복될 수 있음 → 단일 upsert 문 내 중복 제거
    # (Postgres ON CONFLICT는 한 문에서 같은 행을 두 번 못 갱침, code 21000)
    payload = [{"user_id": user_id, "url": u} for u in dict.fromkeys(urls)]
    _sb.table("sent_news").upsert(payload, on_conflict="user_id,url").execute()
