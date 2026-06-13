-- stock_news 스키마
-- Supabase SQL Editor에 그대로 붙여 실행하세요.
-- 회원(auth.users)은 Supabase Auth가 관리하므로 따로 만들지 않습니다.

-- ============================================================
-- 1. stock — 종목 마스터 (검색/자동완성용, 공개 읽기)
-- ============================================================
create table if not exists stock (
    id      bigint generated always as identity primary key,
    ticker  text not null,
    market  text not null check (market in ('KR', 'US')),
    name    text not null,
    unique (ticker, market)
);

-- 검색(이름/티커 부분일치)용 인덱스
create index if not exists idx_stock_name   on stock (name);
create index if not exists idx_stock_ticker on stock (ticker);

-- ============================================================
-- 2. watchlist — 회원 ↔ 종목 M:N 조인
-- ============================================================
create table if not exists watchlist (
    user_id    uuid   not null references auth.users (id) on delete cascade,
    stock_id   bigint not null references stock (id)      on delete cascade,
    created_at timestamptz not null default now(),
    primary key (user_id, stock_id)
);

create index if not exists idx_watchlist_user on watchlist (user_id);

-- ============================================================
-- 3. sent_news — 회원별 발송 중복 방지 로그
-- ============================================================
create table if not exists sent_news (
    user_id uuid not null references auth.users (id) on delete cascade,
    url     text not null,
    sent_at timestamptz not null default now(),
    primary key (user_id, url)
);

-- ============================================================
-- RLS (행 수준 보안) — 켜고 정책을 박는다
-- ============================================================

-- stock: 누구나 읽기 가능(검색용), 쓰기는 막음(시드는 service_role로)
alter table stock enable row level security;
create policy "stock public read"
    on stock for select
    using (true);

-- watchlist: 본인 행만 조회/추가/삭제
alter table watchlist enable row level security;
create policy "own watchlist"
    on watchlist for all
    using (user_id = auth.uid())
    with check (user_id = auth.uid());

-- sent_news: 본인 것만 (브라우저에서 건드릴 일은 없지만 안전하게)
alter table sent_news enable row level security;
create policy "own sent_news"
    on sent_news for all
    using (user_id = auth.uid())
    with check (user_id = auth.uid());

-- 참고: Python 파이프라인은 service_role 키로 접속하므로 RLS를 우회하여
--       모든 회원의 watchlist를 읽고 sent_news를 기록합니다.
