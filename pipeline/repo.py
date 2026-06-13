"""Supabase 데이터 접근 — service_role 키로 RLS 우회(전 회원 조회)."""
import os

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

_sb = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"],
)


def load_members() -> list[dict]:
    """
    전 회원의 watchlist를 회원 단위로 묶어 반환.
    [{user_id, email, stocks: [{ticker, market, name}, ...]}, ...]
    """
    rows = (
        _sb.table("watchlist")
        .select("user_id, stock(ticker, market, name)")
        .execute()
        .data
    )

    by_user: dict[str, list[dict]] = {}
    for r in rows:
        by_user.setdefault(r["user_id"], []).append(r["stock"])

    members = []
    for user_id, stocks in by_user.items():
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
    payload = [{"user_id": user_id, "url": u} for u in urls]
    _sb.table("sent_news").upsert(payload, on_conflict="user_id,url").execute()
