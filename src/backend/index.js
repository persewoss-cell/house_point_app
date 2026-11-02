// 서버 없이 브라우저에서 바로 처리하는 "API" 입구
// 화면은 기존(zip) 그대로 api("이름", {...})를 부르고, 여기서 Firestore에 직접 읽고 씀
import { ready } from "./firebase.js";
import { buildCtx, ApiError } from "./auth.js";
import session from "./actions/session.js";
import bank from "./actions/bank.js";
import individual from "./actions/individual.js";
import savings, { processMaturities } from "./actions/savings.js";
import invest from "./actions/invest.js";
import jobs, { runAutoPayroll } from "./actions/jobs.js";
import auction from "./actions/auction.js";
import lottery from "./actions/lottery.js";
import goal from "./actions/goal.js";

const ACTIONS = { ...session, ...bank, ...individual, ...savings, ...invest, ...jobs, ...auction, ...lottery, ...goal };

// 자동 처리(적금 만기 지급 + 월급 자동지급): 로그인·새로고침 때 시도 (1분에 한 번까지)
async function runAuto() {
  try {
    await processMaturities();
  } catch (e) {
    console.error("적금 만기 자동 처리 실패", e);
  }
  try {
    await runAutoPayroll();
  } catch (e) {
    console.error("월급 자동지급 실패", e);
  }
}
const NO_LOGIN = new Set(["login", "admin_status", "admin_setup", "session"]);

function friendly(e) {
  const code = String((e && e.code) || "");
  if (code.includes("permission-denied")) return "데이터 접근이 거부됐어요. Firestore 보안 규칙(firestore.rules)을 확인해 주세요.";
  if (code.includes("failed-precondition") && String(e.message || "").includes("index")) {
    console.error(e);
    return "Firestore 색인(index)이 필요해요. 브라우저 개발자도구(F12) 콘솔에 나온 링크를 눌러 색인을 만들어 주세요.";
  }
  if (code.includes("unavailable")) return "인터넷 연결을 확인해 주세요.";
  return `오류: ${(e && e.message) || e}`;
}

export async function callAction(action, args, session) {
  try {
    await ready();
    const fn = ACTIONS[action];
    if (!fn) return { ok: false, error: `알 수 없는 요청: ${action}` };
    const ctx = await buildCtx(session);
    // 저장된 로그인이 더 이상 유효하지 않음(비밀번호 변경·계정 삭제) → 화면에서 바로 로그아웃
    if (session && !ctx.role && !NO_LOGIN.has(action)) return { ok: false, auth_lost: true, error: "로그인이 풀렸어요. 다시 로그인해 주세요." };
    if ((action === "session" && ctx.role) || action === "login") await runAuto();
    const out = await fn(ctx, args || {});
    return { ok: true, ...(out || {}) };
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.userMessage };
    console.error(e);
    return { ok: false, error: friendly(e) };
  }
}
