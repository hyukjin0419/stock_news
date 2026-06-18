const { url, publishableKey } = window.SUPABASE_CONFIG;
const sb = supabase.createClient(url, publishableKey);

const $ = (id) => document.getElementById(id);
let debounce, toastTimer;

// ---------- 구독/플랜 ----------
const FREE_LIMIT = 3;
// 구독 입금 계좌 (계좌이체 방식)
const BANK_NUMBER = "1000-4489-5167";
const BANK_INFO = `토스뱅크 ${BANK_NUMBER} (예금주 최혁진)`;
let myPlan = "free"; // 'free' | 'free_legacy' | 'paid'
let watchCount = 0;

const isUnlimited = () => myPlan === "free_legacy" || myPlan === "paid";

async function loadPlan() {
  // RLS상 본인 행만 조회됨. 행이 없으면 무료.
  const { data } = await sb.from("subscriber").select("plan").maybeSingle();
  myPlan = data?.plan || "free";
}

function showUpgrade(show) {
  $("bankInfo").textContent = BANK_INFO;
  $("upgrade").classList.toggle("hidden", !show);
}

$("copyBtn").onclick = () => {
  navigator.clipboard
    .writeText(BANK_NUMBER)
    .then(() => toast("계좌번호 복사됨"))
    .catch(() => toast("복사 실패 — 직접 입력해주세요", true));
};

function toast(msg, isError = false) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.toggle("error", isError);
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 2000);
}

// ---------- 인증 ----------
function _creds() {
  return { email: $("email").value.trim(), password: $("password").value };
}

$("loginBtn").onclick = async () => {
  const { email, password } = _creds();
  if (!email || !password) {
    $("authMsg").textContent = "이메일과 비밀번호를 입력하세요.";
    toast("이메일과 비밀번호를 입력하세요", true);
    return;
  }
  $("authMsg").textContent = "로그인 중...";
  toast("로그인 중...");
  const { error } = await sb.auth.signInWithPassword({ email, password });
  if (error) {
    $("authMsg").textContent = "로그인 실패: " + error.message;
    toast("로그인 실패", true);
  } else {
    $("authMsg").textContent = "";
    toast("로그인 성공");
  }
};

$("signupBtn").onclick = async () => {
  const { email, password } = _creds();
  if (!email || !password) {
    $("authMsg").textContent = "이메일과 비밀번호를 입력하세요.";
    toast("이메일과 비밀번호를 입력하세요", true);
    return;
  }
  $("authMsg").textContent = "가입 중...";
  toast("가입 중...");
  const { data, error } = await sb.auth.signUp({ email, password });
  if (error) {
    $("authMsg").textContent = "가입 실패: " + error.message;
    toast("가입 실패", true);
    return;
  }
  if (data.session) {
    $("authMsg").textContent = "";
    toast("가입 완료");
  } else {
    $("authMsg").textContent = "가입 완료! 이메일 인증 후 로그인하세요.";
    toast("가입 완료 — 이메일 인증 필요");
  }
};

$("logoutBtn").onclick = async () => {
  await sb.auth.signOut();
  location.reload();
};

// 로그인 상태에 따라 화면 전환
sb.auth.onAuthStateChange((_event, session) => render(session));
sb.auth.getSession().then(({ data }) => render(data.session));

function render(session) {
  const logged = !!session;
  $("auth").classList.toggle("hidden", logged);
  $("app").classList.toggle("hidden", !logged);
  if (logged) {
    $("who").textContent = session.user.email;
    loadPlan().then(loadWatchlist);
  }
}

// ---------- 종목 검색 ----------
$("search").oninput = () => {
  clearTimeout(debounce);
  debounce = setTimeout(searchStocks, 250);
};

async function searchStocks() {
  const q = $("search").value.trim();
  if (!q) return ($("results").innerHTML = "");
  const { data, error } = await sb
    .from("stock")
    .select("id, ticker, market, name")
    .or(`name.ilike.%${q}%,ticker.ilike.%${q}%`)
    .limit(10);
  if (error) return console.error(error);
  $("results").innerHTML = data
    .map(
      (s) => `<div class="item">
        <span>${s.name} <span class="muted">${s.ticker}</span>
          <span class="tag ${s.market}">${s.market}</span></span>
        <button data-add="${s.id}" data-name="${s.name}">추가</button>
      </div>`
    )
    .join("");
  document.querySelectorAll("[data-add]").forEach((b) => {
    b.onclick = () => addStock(Number(b.dataset.add), b.dataset.name);
  });
}

// ---------- watchlist 추가/삭제 ----------
async function addStock(stockId, name) {
  // 무료 회원이 한도를 채웠으면 추가 막고 구독 안내
  if (!isUnlimited() && watchCount >= FREE_LIMIT) {
    toast(`무료는 종목 ${FREE_LIMIT}개까지예요`, true);
    showUpgrade(true);
    return;
  }
  const { data: u } = await sb.auth.getUser();
  const { error } = await sb
    .from("watchlist")
    .insert({ user_id: u.user.id, stock_id: stockId });
  if (error) {
    toast(error.code === "23505" ? "이미 추가된 종목이에요" : "추가 실패: " + error.message,
          error.code !== "23505");
  } else {
    toast(`'${name}' 추가됨`);
  }
  loadWatchlist();
}

async function removeStock(stockId, name) {
  const { error } = await sb.from("watchlist").delete().eq("stock_id", stockId);
  toast(error ? "삭제 실패: " + error.message : `'${name}' 삭제됨`, !!error);
  loadWatchlist();
}

async function loadWatchlist() {
  const { data, error } = await sb
    .from("watchlist")
    .select("stock_id, stock(ticker, market, name)")
    .order("created_at", { ascending: false });
  if (error) return console.error(error);

  watchCount = data.length;
  // 종목 수 표시 (무료는 'n/3', 무제한은 'n')
  $("count").textContent = isUnlimited()
    ? `(${watchCount})`
    : `(${watchCount}/${FREE_LIMIT})`;
  // 무료 + 한도 도달 시 구독 안내 노출
  showUpgrade(!isUnlimited() && watchCount >= FREE_LIMIT);

  if (!data.length)
    return ($("watchlist").innerHTML =
      '<p class="muted">아직 없어요. 위에서 검색해 추가하세요.</p>');
  $("watchlist").innerHTML = data
    .map(
      (w) => `<div class="item">
        <span>${w.stock.name} <span class="muted">${w.stock.ticker}</span>
          <span class="tag ${w.stock.market}">${w.stock.market}</span></span>
        <button class="ghost" data-del="${w.stock_id}" data-name="${w.stock.name}">삭제</button>
      </div>`
    )
    .join("");
  document.querySelectorAll("[data-del]").forEach((b) => {
    b.onclick = () => removeStock(Number(b.dataset.del), b.dataset.name);
  });
}
