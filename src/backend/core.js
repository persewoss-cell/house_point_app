// 핵심 로직 (기존 app.py의 api_* / helper 함수를 Firestore 그대로 옮김)
// 잔액 변경은 Firestore 트랜잭션으로 처리해서 동시에 눌러도 금액이 어긋나지 않게 함
import { getOne, find, where, orderBy, qlimit, ref, tx, serverTimestamp, batchWrite } from "./db.js";
import { fail } from "./auth.js";
import { toInt, toFloat, str, toDate, fmtKrDatetime } from "../shared/format.js";

export const UNIT = "포인트";

// -------------------------------------------------
// 통장 거래 (기존 api_add_tx / api_admin_add_tx_by_student_id)
// amount: +입금 / -출금. checkBalance=true면 잔액보다 큰 출금은 거절
// -------------------------------------------------
export async function applyTx({ sid, memo, amount, type, recorder, checkBalance = false, extra = {} }) {
  sid = str(sid);
  amount = toInt(amount);
  if (!sid) fail("계정 정보가 없습니다.");
  const sRef = ref("students", sid);
  const tRef = ref("transactions");
  const newBal = await tx(async (t) => {
    const snap = await t.get(sRef);
    if (!snap.exists()) fail("계정을 찾지 못했습니다.");
    const bal = toInt(snap.data().balance);
    if (checkBalance && amount < 0 && bal < -amount) fail("잔액보다 큰 출금은 불가합니다.");
    const nb = bal + amount;
    t.update(sRef, { balance: nb });
    t.set(tRef, {
      student_id: sid,
      type,
      amount,
      balance_after: nb,
      memo: str(memo),
      recorded_by_name: str(recorder),
      ...extra,
      created_at: serverTimestamp(),
    });
    return nb;
  });
  return { balance: newBal, tx_id: tRef.id };
}

// 입금/출금 중 하나만 (기존 검사 문구 그대로)
export function checkTradeInput(memo, deposit, withdraw) {
  memo = str(memo).trim();
  deposit = toInt(deposit);
  withdraw = toInt(withdraw);
  if (!memo) fail("내역이 필요합니다.");
  if (deposit < 0 || withdraw < 0) fail("금액은 0보다 커야 합니다.");
  if ((deposit > 0 && withdraw > 0) || (deposit === 0 && withdraw === 0)) fail("입금/출금 중 하나만 입력하세요.");
  return { memo, deposit, withdraw, amount: deposit > 0 ? deposit : -withdraw, type: deposit > 0 ? "deposit" : "withdraw" };
}

export function isSavingsMemo(memo) {
  memo = str(memo);
  return memo.includes("적금 가입") || memo.includes("적금 해지") || memo.includes("적금 만기") || memo.includes("적금 중도해지");
}

export function isInvestMemo(memo, type = "") {
  memo = str(memo).trim();
  return memo.includes("투자") || str(type).startsWith("invest");
}

// 이 거래가 기존 앱의 "되돌리기"로 이미 되돌려졌는지 (related_tx)
export async function rolledBackIds(sid) {
  const docs = await find("transactions", where("student_id", "==", str(sid)), where("type", "==", "rollback"));
  return new Set(docs.map((d) => str(d.related_tx)).filter(Boolean));
}

// 통장 거래 내역 (최신순)
export async function getTxDocs(sid, limit = 200) {
  return await find("transactions", where("student_id", "==", str(sid)), orderBy("created_at", "desc"), qlimit(toInt(limit) || 200));
}

export function txRow(t, rolled = null) {
  const amt = toInt(t.amount);
  const dt = toDate(t.created_at);
  return {
    tx_id: String(t._id),
    created_at_kr: dt ? fmtKrDatetime(dt) : "",
    memo: str(t.memo),
    recorder: str(t.recorded_by_name || t.recorder),
    type: str(t.type),
    amount: amt,
    deposit: amt > 0 ? amt : 0,
    withdraw: amt < 0 ? -amt : 0,
    balance_after: toInt(t.balance_after),
    rolled_back: rolled ? rolled.has(String(t._id)) : false,
    _ts: dt ? dt.getTime() : 0,
  };
}

export async function getTxRows(sid, limit = 200) {
  const [docs, rolled] = await Promise.all([getTxDocs(sid, limit), rolledBackIds(sid)]);
  return docs.map((t) => txRow(t, rolled)).sort((a, b) => b._ts - a._ts);
}

// 되돌리기/삭제가 가능한 거래인지 (적금·투자·되돌리기 기록은 보호)
export function canRemove(t, rolled) {
  const ty = str(t.type);
  const memo = str(t.memo);
  if (ty === "rollback" || memo.includes("되돌리기")) return false;
  if (isSavingsMemo(memo) || ty === "maturity") return false;
  if (isInvestMemo(memo, ty)) return false;
  if (rolled && rolled.has(String(t._id))) return false;
  return true;
}

// 거래 기록 자체를 지우고 잔액을 원래대로 + 그 뒤 기록들의 "총액"도 지운 금액만큼 정정
export async function removeTx(t) {
  const sid = str(t.student_id);
  const amount = toInt(t.amount);
  const sRef = ref("students", sid);
  const tRef = ref("transactions", t._id);
  const ok = await tx(async (x) => {
    const tSnap = await x.get(tRef);
    if (!tSnap.exists()) return false;
    const sSnap = await x.get(sRef);
    x.delete(tRef);
    if (sSnap.exists()) x.update(sRef, { balance: toInt(sSnap.data().balance) - amount });
    return true;
  });
  if (!ok) return false;
  const base = toDate(t.created_at);
  if (base) {
    const later = (await getTxDocs(sid, 1000)).filter((d) => {
      const dt = toDate(d.created_at);
      return dt && dt > base;
    });
    await batchWrite(later.map((d) => ({ type: "update", ref: ref("transactions", d._id), data: { balance_after: toInt(d.balance_after) - amount } })));
  }
  return true;
}

// -------------------------------------------------
// 계정
// -------------------------------------------------
export async function activeStudents() {
  const docs = await find("students", where("is_active", "==", true));
  return docs.map((d) => ({ ...d, student_id: String(d._id) }));
}

// 기존 api_list_accounts_cached: 이름순
export async function listAccounts() {
  const rows = (await activeStudents())
    .filter((s) => str(s.name))
    .map((s) => ({ student_id: s.student_id, no: toInt(s.no), name: str(s.name), balance: toInt(s.balance) }));
  rows.sort((a, b) => a.name.localeCompare(b.name, "ko"));
  return rows;
}

// -------------------------------------------------
// 직업명 (기존 _get_role_name_by_student_id)
// -------------------------------------------------
export async function loadRoleLookup() {
  const [roles, jobs] = await Promise.all([find("roles"), find("job_salary")]);
  const roleById = {};
  for (const r of roles) roleById[String(r._id)] = str(r.role_name || r.name || r._id).trim() || String(r._id);
  const jobsByStudent = {};
  for (const j of jobs) {
    const jname = str(j.job || j.role_name).trim();
    if (!jname) continue;
    for (const sid of (j.assigned_ids || []).map(String)) {
      if (!jobsByStudent[sid]) jobsByStudent[sid] = [];
      if (!jobsByStudent[sid].includes(jname)) jobsByStudent[sid].push(jname);
    }
  }
  return { roleById, jobsByStudent };
}

export function roleNameFor(s, sid, lookup) {
  if (s) {
    const direct = str(s.job_name || s.job).trim();
    if (direct) return direct;
    const rid = str(s.role_id || s.job_role_id || s.job_id).trim();
    if (rid) return lookup.roleById[rid] ?? rid;
  }
  const jobs = lookup.jobsByStudent[String(sid)] || [];
  return jobs.length ? jobs.join(", ") : "없음";
}

// -------------------------------------------------
// 투자 요약 (기존 _get_invest_summary_by_student_id / _get_invest_principal_by_student_id)
// 현재평가 = 투자금 + 투자금 × (현재가 − 매입가) / 10, 차이가 −100 이하면 0
// -------------------------------------------------
const price1 = (v) => Number(toFloat(v, 0).toFixed(1));

export async function loadInvestProductMap() {
  const docs = await find("invest_products");
  const m = {};
  for (const x of docs) {
    const pid = str(x.product_id || x._id);
    const name = str(x.name).trim() || str(x.label).trim() || str(x.title).trim() || str(x.subject).trim() || pid;
    m[pid] = { name, cur: toFloat(x.current_price, 0) };
  }
  return m;
}

export function investSummary(ledgerRows, prodMap) {
  const val = {};
  const prin = {};
  for (const x of ledgerRows) {
    if (x.redeemed) continue;
    const pid = str(x.product_id);
    if (!pid) continue;
    const p = prodMap[pid] || { name: pid, cur: 0 };
    const amt = toInt(x.invest_amount);
    const diff = price1(p.cur - toFloat(x.buy_price, 0));
    let cur = diff <= -100 ? 0 : amt + (amt * diff) / 10;
    if (cur < 0) cur = 0;
    val[pid] = (val[pid] || 0) + cur;
    if (amt > 0) prin[pid] = (prin[pid] || 0) + amt;
  }
  const nameOf = (pid) => (prodMap[pid] ? prodMap[pid].name : pid);
  const vItems = Object.entries(val).sort((a, b) => b[1] - a[1]);
  let evalText = vItems.slice(0, 3).map(([pid, v]) => `${nameOf(pid)} ${Math.round(v)}${UNIT}`).join(", ");
  if (vItems.length > 3) evalText += ` 외 ${vItems.length - 3}개`;
  const pItems = Object.entries(prin).sort((a, b) => nameOf(a[0]).localeCompare(nameOf(b[0]), "ko"));
  return {
    evalText: vItems.length ? evalText : "없음",
    evalTotal: Math.round(vItems.reduce((s, [, v]) => s + v, 0)),
    prinText: pItems.length ? pItems.map(([pid, v]) => `${nameOf(pid)} ${v}${UNIT}`).join(", ") : "없음",
    prinTotal: pItems.reduce((s, [, v]) => s + v, 0),
  };
}

export async function investSummaryFor(sid, prodMap = null) {
  const [ledger, pm] = await Promise.all([find("invest_ledger", where("student_id", "==", str(sid))), prodMap ? prodMap : loadInvestProductMap()]);
  return investSummary(ledger, pm);
}

// 적금 총액 (진행 중인 적금 원금 합)
export async function savingsTotalFor(sid) {
  const docs = await find("savings", where("student_id", "==", str(sid)));
  let total = 0;
  for (const x of docs) {
    const st = str(x.status || "active").toLowerCase().trim();
    if (st === "active" || st === "running") total += toInt(x.principal);
  }
  return total;
}

export { getOne };
