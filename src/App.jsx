import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, getToken, setToken, remember, onBusy, onAuthLost } from "./lib/api.js";
import { AppCtx, Cols, TextInput, Checkbox, Btn, ErrorBox, Toasts, Loading, Info, prefetch, clearLoadCache } from "./components/ui.jsx";
import { StudentPinModal, AdminAccountModal } from "./components/AccountModals.jsx";
import UserHeader from "./components/UserHeader.jsx";
import { BankAdmin, BankStudent } from "./tabs/Bank.jsx";
import Individual from "./tabs/Individual.jsx";
import Savings from "./tabs/Savings.jsx";
import Invest from "./tabs/Invest.jsx";
import Jobs from "./tabs/Jobs.jsx";
import Auction from "./tabs/Auction.jsx";
import Lottery from "./tabs/Lottery.jsx";
import Goal from "./tabs/Goal.jsx";
import { configMissing } from "./backend/firebase.js";

// 메뉴에 보이는 아이콘만 더 귀엽게 (권한 이름·저장 값은 그대로)
const ICON_SWAP = { "🔎": "🔍", "🏦": "🐷", "⭐": "🔑", "🏷️": "🔨", "🧾": "📜", "📝": "📒" };
// 메뉴 한 줄에 딱 맞도록 짧게 보이는 이름 (권한·탭 이름은 그대로)
const MENU_SHORT = { "은행(적금)": "적금" };
function menuLabel(label) {
  let extra = false;
  let s = String(label || "");
  if (s.startsWith("⍟")) {
    extra = true;
    s = s.slice(1);
  }
  const m = s.match(/^(\p{Extended_Pictographic}\uFE0F?)\s*(.*)$/u);
  const icon = m ? ICON_SWAP[m[1]] || m[1] : "";
  let text = (m ? m[2] : s).replace(/\(관리자\)$/, "").trim();
  text = MENU_SHORT[text] || text;
  return { icon, text, extra };
}

// 탭별로 화면이 처음 불러오는 데이터 (로그인 직후 미리 불러 두면 탭을 누를 때 바로 뜸)
const TAB_LOADS = {
  "🏦 내 통장": (admin) => (admin ? [["templates_list", {}], ["accounts_list", {}]] : [["templates_list", {}], ["tx_list", { limit: 300 }]]),
  "🔎 개별조회": () => [["individual_students", {}]],
  "💼 직업/월급": () => [["jobs_load", {}]],
  "🏦 은행(적금)": () => [["savings_load", {}]],
  "📈 투자": (admin) => [["invest_load", { admin_mode: admin }]],
  "🏷️ 경매": (admin) => (admin ? [["auction_admin_load", { pick_round_id: "" }]] : [["auction_user_load", {}]]),
  "🍀 복권": (admin) => (admin ? [] : [["lottery_user_load", {}]]),
  "🎯 목표": () => [["goal_load", {}]],
};

// 관리자 탭 (기존 우리집 앱 순서: 입금/출금 · 개별조회 · 직업/월급 · 투자 · 경매 · 복권)
const ADMIN_TABS = ["🏦 내 통장", "🔎 개별조회", "💼 직업/월급", "📈 투자", "🏷️ 경매", "🍀 복권"];

function buildTabs(user) {
  if (!user) return { keys: [], labels: {} };
  if (user.role === "admin") {
    const labels = {};
    ADMIN_TABS.forEach((t) => (labels[t] = t === "🏦 내 통장" ? "💰입금/출금" : t));
    return { keys: [...ADMIN_TABS], labels };
  }
  // 가족 탭 (기존: 거래/통장 · 적금 · 투자 · 목표 · 경매 · 복권)
  const keys = ["🏦 내 통장", "🏦 은행(적금)"];
  if (user.invest_enabled !== false) keys.push("📈 투자");
  keys.push("🎯 목표", "🏷️ 경매", "🍀 복권");
  const labels = { "🏦 내 통장": "📝 통장/거래", "🏦 은행(적금)": "🏦 적금" };
  return { keys, labels };
}

// 처음 한 번: 관리자 비밀번호 정하기
function AdminSetup({ onDone, onCancel }) {
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [err, setErr] = useState("");
  const run = async () => {
    setErr("");
    const r = await api("admin_setup", { new_pin: a, new_pin2: b });
    if (!r.ok) return setErr(r.error || "설정 실패");
    remember.write({ name: "", pin: "", rememberName: false, rememberPin: false });
    onDone(r.session);
  };
  return (
    <div className="stack login-form">
      <Info>관리자 비밀번호가 아직 없어요. 처음 한 번만 정해 주세요. (4자 이상, 영문+숫자로 길게 정할수록 안전해요)</Info>
      <Cols w={[1, 1]}>
        <TextInput label="새 관리자 비밀번호" type="password" value={a} onChange={setA} />
        <TextInput label="새 관리자 비밀번호(확인)" type="password" value={b} onChange={setB} onEnter={run} />
      </Cols>
      <Cols w={[2, 1]}>
        <Btn className="primary big" onClick={run}>관리자 비밀번호 저장</Btn>
        <Btn onClick={onCancel}>취소</Btn>
      </Cols>
      <ErrorBox>{err}</ErrorBox>
    </div>
  );
}

function LoginForm({ onLogin }) {
  const saved = useMemo(() => remember.read(), []);
  const [name, setName] = useState(saved.name);
  const [pin, setPin] = useState(saved.pin);
  const [rn, setRn] = useState(saved.rememberName);
  const [rp, setRp] = useState(saved.rememberPin);
  const [err, setErr] = useState("");
  const [setup, setSetup] = useState(false);
  const submit = async () => {
    setErr("");
    const n = name.trim();
    const p = pin.trim();
    if (!n) return setErr("이름을 입력해 주세요.");
    const r = await api("login", { name: n, pin: p });
    if (!r.ok) return setErr(r.error || "로그인 실패");
    if (r.need_admin_setup) return setSetup(true);
    remember.write({ name: n, pin: p, rememberName: rn, rememberPin: rp });
    onLogin(r.session, r.user.role === "admin" ? ["관리자 모드 ON", "🔓"] : ["로그인 완료!", "✅"]);
  };
  if (setup) return <AdminSetup onCancel={() => setSetup(false)} onDone={(sess) => onLogin(sess, ["관리자 비밀번호 저장 완료! 관리자 모드 ON", "🔓"])} />;
  return (
    <div className="stack login-form">
      <Cols w={[1, 1]}>
        <TextInput label="이름" value={name} onChange={setName} onEnter={submit} autoComplete="username" />
        <TextInput label="비밀번호(4자리)" type="password" value={pin} onChange={setPin} onEnter={submit} autoComplete="current-password" />
      </Cols>
      <Cols w={[1, 1]}>
        <Checkbox label="아이디 기억하기" checked={rn} onChange={setRn} />
        <Checkbox label="비밀번호 기억하기" checked={rp} onChange={setRp} />
      </Cols>
      <Btn className="primary big" onClick={submit}>로그인</Btn>
      <ErrorBox>{err}</ErrorBox>
    </div>
  );
}

function TabContent({ tab, user }) {
  const isAdmin = user.role === "admin";
  switch (tab) {
    case "🏦 내 통장":
      return isAdmin ? <BankAdmin /> : <BankStudent />;
    case "🔎 개별조회":
      return <Individual />;
    case "💼 직업/월급":
      return <Jobs />;
    case "🏦 은행(적금)":
      return <Savings />;
    case "📈 투자":
      return <Invest adminMode={isAdmin} />;
    case "🏷️ 경매":
      return <Auction />;
    case "🍀 복권":
      return <Lottery />;
    case "🎯 목표":
      return <Goal />;
    default:
      return <Info>🚧 이 메뉴는 다음 단계에서 옮겨 올 예정이에요.</Info>;
  }
}

export default function App() {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(true);
  const [pop, setPop] = useState(""); // "pin" | "acc"
  const [toasts, setToasts] = useState([]);
  const [ver, setVer] = useState(0);
  const [active, setActive] = useState(null);
  const [busy, setBusy] = useState(false);
  const tid = useRef(0);

  useEffect(() => onBusy(setBusy), []);

  const toast = useCallback((msg, icon = "✅") => {
    const id = ++tid.current;
    setToasts((t) => [...t, { id, msg, icon }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4000);
  }, []);

  const loadSession = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      return null;
    }
    const r = await api("session");
    if (r.ok && r.user) {
      setUser(r.user);
      return r.user;
    }
    if (r.ok && !r.user) {
      setToken("");
      setUser(null);
    }
    return null;
  }, []);

  useEffect(() => {
    (async () => {
      await loadSession();
      setBooting(false);
    })();
  }, [loadSession]);

  // 권한이 바뀌면 바로 반영되도록(기존 앱처럼) 화면이 바뀔 때마다 권한 다시 확인
  const refresh = useCallback(() => {
    setVer((v) => v + 1);
    loadSession();
  }, [loadSession]);

  const tabs = useMemo(() => buildTabs(user), [user]);
  const prefetched = useRef("");
  useEffect(() => {
    if (!user) return;
    const who = `${user.role}:${user.sid || ""}`;
    if (prefetched.current === who) return;
    prefetched.current = who;
    const admin = user.role === "admin";
    const list = [];
    if (!admin) list.push(["user_header", {}]);
    for (const k of tabs.keys) list.push(...((TAB_LOADS[k] && TAB_LOADS[k](admin)) || []));
    prefetch(list);
  }, [user, tabs]);
  useEffect(() => {
    if (!user) return;
    if (!active || !tabs.keys.includes(active)) setActive(tabs.keys[0] || null);
  }, [user, tabs, active]);

  const onLogin = async (sess, [msg, icon]) => {
    clearLoadCache();
    prefetched.current = "";
    setToken(sess);
    setActive(null);
    await loadSession();
    toast(msg, icon);
  };

  const logout = () => {
    clearLoadCache();
    prefetched.current = "";
    setToken("");
    setUser(null);
    setActive(null);
  };

  useEffect(
    () =>
      onAuthLost(() => {
        if (!user) return;
        logout();
        toast("로그인이 풀렸어요. 다시 로그인해 주세요.", "🔒");
      }),
    [user] // eslint-disable-line react-hooks/exhaustive-deps
  );

  const ctx = useMemo(() => ({ user, toast, refresh, ver }), [user, toast, refresh, ver]);

  return (
    <AppCtx.Provider value={ctx}>
      <div className="app">
        {busy ? <div className="top-loading" /> : null}
        <main className="main">
          {user && user.role === "admin" ? (
            <header className="topbar admin-bar">
              <div className="brand">
                <span className="brand-logo">🏠</span>
                <div>
                  <div className="brand-title">우리집 포인트 통장</div>
                  <div className="brand-sub">우리 가족 포인트 놀이터 🪙</div>
                </div>
              </div>
              <div className="who">
                <span className="who-chip">👑 관리자</span>
                <Btn full={false} className="ghost" onClick={() => setPop("acc")}>
                  🔐 계정관리
                </Btn>
                <Btn full={false} className="ghost" onClick={logout}>
                  로그아웃
                </Btn>
              </div>
            </header>
          ) : null}
          {configMissing ? (
            <ErrorBox>Firebase 설정이 비어 있어요. 깃허브에서 src/firebaseConfig.js 파일에 Firebase 웹 앱 설정값을 넣어 주세요. (README 2단계 참고)</ErrorBox>
          ) : booting ? (
            <Loading />
          ) : !user ? (
            <div className="login-card">
              <div className="brand center login-brand">
                <span className="brand-logo">🏠</span>
                <div>
                  <div className="brand-title">우리집 포인트 통장</div>
                  <div className="brand-sub">우리 가족 포인트 놀이터 🪙</div>
                </div>
              </div>
              <div className="login-title">로그인</div>
              <div className="login-sub">이름과 비밀번호를 입력해 주세요</div>
              <LoginForm onLogin={onLogin} />
            </div>
          ) : (
            <div className="stack">
              {user.role === "student" ? <UserHeader onLogout={logout} onPin={() => setPop("pin")} /> : null}
              <nav className="main-menu" role="radiogroup" aria-label="메인 메뉴">
                {tabs.keys.map((k) => {
                  const { icon, text, extra } = menuLabel(tabs.labels[k] || k);
                  return (
                    <button
                      type="button"
                      key={k}
                      className={`mm ${k === active ? "on" : ""} ${extra ? "extra" : ""}`}
                      onClick={() => {
                        if (k !== active) setActive(k);
                      }}
                    >
                      {icon ? <span className="mm-ic">{icon}</span> : null}
                      <span>{text}</span>
                      {extra ? <span className="mm-badge">관리</span> : null}
                    </button>
                  );
                })}
              </nav>
              {active ? (
                <section className="panel stack" key={active}>
                  <TabContent tab={active} user={user} />
                </section>
              ) : null}
            </div>
          )}
        </main>
        <StudentPinModal open={pop === "pin"} onClose={() => setPop("")} />
        <AdminAccountModal open={pop === "acc"} onClose={() => setPop("")} />
        <Toasts items={toasts} />
      </div>
    </AppCtx.Provider>
  );
}

