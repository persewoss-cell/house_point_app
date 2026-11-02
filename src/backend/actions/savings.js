// 🏦 적금 (기존 우리집 앱 규칙 그대로)
// - 이자율 = 기간(주) × 5%, 기간 1~10주, 원금은 10단위, 잔액 이내
// - 중도 해지는 원금만, 만기면 원금+이자 자동 지급
import { find, getOne, ref, tx, where, serverTimestamp } from "../db.js";
import { fail, requireLogin, requireStudent, ADMIN_NAME } from "../auth.js";
import { str, toInt, toDate, fmtMd, kstParts, pad2 } from "../../shared/format.js";

export const rateByWeeks = (weeks) => toInt(weeks) * 0.05;
const pyRound = (x) => {
  const f = Math.floor(x);
  const d = x - f;
  if (Math.abs(d - 0.5) < 1e-9) return f % 2 === 0 ? f : f + 1;
  return Math.round(x);
};
export const interestFor = (principal, weeks) => pyRound(toInt(principal) * rateByWeeks(weeks));

const STATUS = { active: "진행중", running: "진행중", canceled: "중도해지", cancelled: "중도해지", matured: "만기" };

function ymd(d) {
  const p = kstParts(d);
  return p ? `${p.year}-${pad2(p.month)}-${pad2(p.day)}` : "";
}

function savingsRow(s) {
  const principal = toInt(s.principal);
  const weeks = toInt(s.weeks);
  const interest = toInt(s.interest);
  const st = str(s.status || "active").toLowerCase();
  const maturityAmt = principal + interest;
  return {
    _id: String(s._id),
    _status: st,
    _t: toDate(s.start_date) ? toDate(s.start_date).getTime() : 0,
    적금기간: `${weeks}주`,
    이자율: `${(rateByWeeks(weeks) * 100).toFixed(1)}%`,
    "적금 금액": principal,
    이자: interest,
    만기금액: maturityAmt,
    적금날짜: fmtMd(s.start_date) || "-",
    만기날짜: fmtMd(s.maturity_date) || "-",
    처리결과: STATUS[st] || st,
    지급금액: st === "canceled" || st === "cancelled" ? principal : st === "matured" ? maturityAmt : "-",
  };
}

export async function savingsRowsFor(sid) {
  const docs = await find("savings", where("student_id", "==", str(sid)));
  return docs.map(savingsRow).sort((a, b) => b._t - a._t).slice(0, 50);
}

// 만기 자동 지급 (기존 api_process_maturities): 누가 접속하든 만기된 적금을 모두 처리
let _lastRun = 0;
export async function processMaturities({ force = false } = {}) {
  const now = Date.now();
  if (!force && now - _lastRun < 60000) return 0;
  _lastRun = now;
  let n = 0;
  const active = await find("savings", where("status", "==", "active"));
  for (const s of active) {
    const m = toDate(s.maturity_date);
    if (!m || m.getTime() > now) continue;
    const sid = str(s.student_id);
    if (!sid) continue;
    const amount = toInt(s.principal) + toInt(s.interest);
    const weeks = toInt(s.weeks);
    const svRef = ref("savings", s._id);
    const stRef = ref("students", sid);
    const tRef = ref("transactions");
    try {
      const done = await tx(async (t) => {
        const sv = await t.get(svRef);
        if (!sv.exists() || str(sv.data().status) !== "active") return false;
        const st = await t.get(stRef);
        if (!st.exists()) return false;
        const nb = toInt(st.data().balance) + amount;
        t.update(stRef, { balance: nb });
        t.update(svRef, { status: "matured" });
        t.set(tRef, { student_id: sid, type: "maturity", amount, balance_after: nb, memo: `적금 만기(${weeks}주)`, recorded_by_name: ADMIN_NAME, created_at: serverTimestamp() });
        return true;
      });
      if (done) n += 1;
    } catch (e) {
      console.error("적금 만기 처리 실패", e);
    }
  }
  return n;
}

export default {
  async savings_load(ctx) {
    requireLogin(ctx);
    if (ctx.isAdmin) return { rows: [], balance: 0 };
    const auto = await processMaturities();
    const s = await getOne("students", ctx.sid);
    return { rows: await savingsRowsFor(ctx.sid), balance: toInt(s && s.balance), auto_matured: auto };
  },

  // 적금 가입 (기존 api_savings_create)
  async savings_join(ctx, { principal, weeks }) {
    requireStudent(ctx);
    principal = toInt(principal);
    weeks = toInt(weeks);
    if (principal <= 0) fail("원금은 1 이상이어야 합니다.");
    if (principal % 10 !== 0) fail("원금은 10단위만 가능합니다.");
    if (weeks < 1 || weeks > 10) fail("기간은 1~10주만 가능합니다.");
    const interest = interestFor(principal, weeks);
    const maturity = new Date(Date.now() + weeks * 7 * 86400000);
    const stRef = ref("students", ctx.sid);
    const svRef = ref("savings");
    const tRef = ref("transactions");
    await tx(async (t) => {
      const st = await t.get(stRef);
      const bal = toInt(st.exists() ? st.data().balance : 0);
      if (principal > bal) fail("잔액보다 큰 원금은 가입할 수 없습니다.");
      const nb = bal - principal;
      t.update(stRef, { balance: nb });
      t.set(tRef, { student_id: ctx.sid, type: "withdraw", amount: -principal, balance_after: nb, memo: `적금 가입(${weeks}주)`, recorded_by_name: ctx.name, created_at: serverTimestamp() });
      t.set(svRef, { student_id: ctx.sid, principal, weeks, interest, start_date: serverTimestamp(), maturity_date: maturity, status: "active" });
    });
    return { interest, maturity: ymd(maturity) };
  },

  // 중도 해지 (원금만, 기존 api_savings_cancel)
  async savings_cancel(ctx, { doc_id }) {
    requireStudent(ctx);
    const svRef = ref("savings", doc_id);
    const stRef = ref("students", ctx.sid);
    const tRef = ref("transactions");
    const refunded = await tx(async (t) => {
      const sv = await t.get(svRef);
      if (!sv.exists()) fail("해당 적금을 찾지 못했습니다.");
      const s = sv.data();
      if (str(s.student_id) !== ctx.sid) fail("권한이 없습니다.");
      if (str(s.status) !== "active") fail("이미 처리된 적금입니다.");
      const principal = toInt(s.principal);
      const st = await t.get(stRef);
      const nb = toInt(st.data().balance) + principal;
      t.update(svRef, { status: "canceled" });
      t.update(stRef, { balance: nb });
      t.set(tRef, { student_id: ctx.sid, type: "deposit", amount: principal, balance_after: nb, memo: `적금 해지(${toInt(s.weeks)}주)`, recorded_by_name: ctx.name, created_at: serverTimestamp() });
      return principal;
    });
    return { refunded };
  },
};
