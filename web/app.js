const { url, publishableKey } = window.SUPABASE_CONFIG;
const sb = supabase.createClient(url, publishableKey);

const $ = (id) => document.getElementById(id);
let debounce, toastTimer;

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
  if (!email || !password) return ($("authMsg").textContent = "이메일과 비밀번호를 입력하세요.");
  const { error } = await sb.auth.signInWithPassword({ email, password });
  $("authMsg").textContent = error ? "로그인 실패: " + error.message : "";
};

$("signupBtn").onclick = async () => {
  const { email, password } = _creds();
  if (!email || !password) return ($("authMsg").textContent = "이메일과 비밀번호를 입력하세요.");
  const { data, error } = await sb.auth.signUp({ email, password });
  if (error) return ($("authMsg").textContent = "가입 실패: " + error.message);
  $("authMsg").textContent = data.session
    ? ""
    : "가입 완료! 이메일 인증 후 로그인하세요.";
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
    loadWatchlist();
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
