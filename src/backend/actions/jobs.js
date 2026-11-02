// 💼 직업/월급 : 공제 설정 · 지급 설정(자동/수동) · 직업 지정/해제 · 직업 추가/수정/삭제 · 엑셀
// 기존 우리집 앱 데이터 그대로: config/salary_deductions, config/salary_payroll, job_salary, payroll_log, treasury
import { find, getOne, add, set, update, del, ref, tx, where, serverTimestamp, batchWrite } from "../db.js";
import { fail, requireAdmin, isAdminPin, ADMIN_NAME } from "../auth.js";
import { applyTx, listAccounts } from "../core.js";
import { str, toInt, toFloat, kstParts, pad2 } from "../../shared/format.js";

const orInt = (v, d) => toInt(v, 0) || d; // 파이썬 int(v or d)
const orFloat = (v, d) => toFloat(v, 0) || d;
const pyRound = (x) => {
  const f = Math.floor(x);
  return Math.abs(x - f - 0.5) < 1e-9 ? (f % 2 === 0 ? f : f + 1) : Math.round(x);
};

export async function getSalaryCfg() {
  const d = await getOne("config", "salary_deductions");
  if (!d) return { tax_percent: 10.0, desk_rent: 50, electric_fee: 10, health_fee: 10 };
  return { tax_percent: orFloat(d.tax_percent, 10.0), desk_rent: orInt(d.desk_rent, 50), electric_fee: orInt(d.electric_fee, 10), health_fee: orInt(d.health_fee, 10) };
}

export function calcNet(gross, cfg) {
  gross = toInt(gross);
  const tax = pyRound(gross * (orFloat(cfg.tax_percent, 10) / 100));
  return Math.max(0, gross - tax - orInt(cfg.desk_rent, 50) - orInt(cfg.electric_fee, 10) - orInt(cfg.health_fee, 10));
}

async function getPayrollCfg() {
  const d = await getOne("config", "salary_payroll");
  if (!d) return { pay_day: 17, auto_enabled: false };
  return { pay_day: orInt(d.pay_day, 25), auto_enabled: !!d.auto_enabled };
}

const monthKey = (now = new Date()) => {
  const p = kstParts(now);
  return `${p.year}-${pad2(p.month)}`;
};
const paylogId = (mkey, sid, jobId = "") => `${mkey}_${sid}_${str(jobId).trim() || "_"}`;

async function alreadyPaid(mkey, sid, jobId, jobName) {
  if (await getOne("payroll_log", paylogId(mkey, sid, jobId))) return true;
  const legacy = await getOne("payroll_log", `${mkey}_${sid}`);
  return !!(legacy && str(legacy.job) && str(legacy.job) === str(jobName));
}

async function listJobs() {
  const docs = await find("job_salary");
  return docs
    .map((x) => ({ _id: String(x._id), order: orInt(x.order, 999999), job: str(x.job), salary: toInt(x.salary), assigned_ids: (x.assigned_ids || []).map(String).filter((s) => s.trim()) }))
    .sort((a, b) => a.order - b.order);
}

// 배정된 (가족+직업) 하나하나에 월급 지급 + 공제액은 국고(treasury) 세입 + 지급 기록
async function payAll(method, { skipPaid }) {
  const cfg = await getSalaryCfg();
  const mkey = monthKey();
  const accs = await listAccounts();
  const idToName = Object.fromEntries(accs.map((a) => [a.student_id, a.name]));
  let paid = 0;
  let skipped = 0;
  let err = 0;
  for (const job of await listJobs()) {
    const net = calcNet(job.salary, cfg);
    if (net <= 0) continue;
    for (const sid of job.assigned_ids) {
      if (!(sid in idToName)) continue; // 삭제된 계정은 지급 안 함
      if (skipPaid && (await alreadyPaid(mkey, sid, job._id, job.job))) {
        skipped += 1;
        continue;
      }
      try {
        await applyTx({ sid, memo: `월급 ${job.job}`, amount: net, type: "deposit", recorder: ADMIN_NAME });
        const ded = Math.max(0, job.salary - net);
        if (ded > 0) {
          const nm = idToName[sid] || "";
          await add("treasury", { memo: `월급 공제 세입(${mkey}) ${job.job}` + (nm ? ` - ${nm}` : ""), income: ded, expense: 0, actor: "system_salary", created_at: new Date().toISOString() });
        }
        await set("payroll_log", paylogId(mkey, sid, job._id), { month: mkey, student_id: sid, amount: net, job: job.job, job_id: job._id, method, paid_at: serverTimestamp() }, true);
        paid += 1;
      } catch (e) {
        console.error("월급 지급 실패", e);
        err += 1;
      }
    }
  }
  return { paid, skipped, err };
}

// 월급 자동지급: 지급일부터 그 달 안에 누군가 접속하면 한 번만 (이미 받은 사람은 건너뜀)
let _lastRun = 0;
export async function runAutoPayroll({ force = false } = {}) {
  const now = Date.now();
  if (!force && now - _lastRun < 60000) return null;
  _lastRun = now;
  const pc = await getPayrollCfg();
  if (!pc.auto_enabled) return null;
  const kp = kstParts(new Date());
  const last = new Date(Date.UTC(kp.year, kp.month, 0)).getUTCDate();
  const payDay = Math.min(Math.max(1, pc.pay_day), last);
  if (kp.day < payDay) return null;
  const lockId = `${monthKey()}_${pad2(payDay)}`;
  const lockRef = ref("payroll_auto_run", lockId);
  const got = await tx(async (t) => {
    const s = await t.get(lockRef);
    if (s.exists()) return false;
    t.set(lockRef, { month: monthKey(), pay_day: payDay, run_at: serverTimestamp(), source: "auto_web" });
    return true;
  });
  if (!got) return null;
  return await payAll("auto", { skipPaid: true });
}

export default {
  async jobs_load(ctx) {
    requireAdmin(ctx);
    const [cfg, payroll, rows, accs] = await Promise.all([getSalaryCfg(), getPayrollCfg(), listJobs(), listAccounts()]);
    const mkey = monthKey();
    let alreadyAny = false;
    for (const r of rows) {
      if (calcNet(r.salary, cfg) <= 0) continue;
      for (const sid of r.assigned_ids) {
        if (await alreadyPaid(mkey, sid, r._id, r.job)) {
          alreadyAny = true;
          break;
        }
      }
      if (alreadyAny) break;
    }
    return { cfg, payroll, rows, students: accs.map((a) => ({ student_id: a.student_id, name: a.name })), already_any: alreadyAny };
  },

  async salary_cfg_save(ctx, { tax_percent, desk_rent, electric_fee, health_fee }) {
    requireAdmin(ctx);
    await set("config", "salary_deductions", { tax_percent: toFloat(tax_percent, 10), desk_rent: toInt(desk_rent), electric_fee: toInt(electric_fee), health_fee: toInt(health_fee), updated_at: serverTimestamp() }, true);
    return {};
  },

  async payroll_cfg_save(ctx, { pay_day, auto_enabled }) {
    requireAdmin(ctx);
    const d = toInt(pay_day, 25);
    if (d < 1 || d > 31) fail("지급 날짜는 1~31일 사이로 정해 주세요.");
    await set("config", "salary_payroll", { pay_day: d, auto_enabled: !!auto_enabled, updated_at: serverTimestamp() }, true);
    return {};
  },

  // 💸 수동지급(이번 달 즉시). 이미 지급 기록이 있으면 관리자 비밀번호 확인 후 재지급
  async payroll_manual(ctx, { admin_pin, confirm_repay }) {
    requireAdmin(ctx);
    if (confirm_repay && !(await isAdminPin(admin_pin))) fail("관리자 비밀번호가 틀립니다.");
    const r = await payAll("manual", { skipPaid: false });
    return { paid: r.paid, err: r.err };
  },

  // 고용 / 해제 (여러 명, 정원 제한 없음)
  async job_assign(ctx, { job_id, sids, op }) {
    requireAdmin(ctx);
    const j = await getOne("job_salary", job_id);
    if (!j) fail("직업을 찾지 못했어요.");
    const assigned = (j.assigned_ids || []).map(String).filter((s) => s.trim());
    sids = (sids || []).map(String).filter(Boolean);
    let next;
    if (op === "hire") next = [...assigned, ...sids.filter((s) => !assigned.includes(s))];
    else next = assigned.filter((s) => !sids.includes(s));
    const changed = next.length !== assigned.length;
    if (changed) await update("job_salary", job_id, { assigned_ids: next, student_count: 0 });
    return { changed };
  },

  // 🔥 전체 직업 해제
  async job_clear_all(ctx) {
    requireAdmin(ctx);
    const rows = await listJobs();
    await batchWrite(rows.map((r) => ({ type: "update", ref: ref("job_salary", r._id), data: { assigned_ids: [], student_count: 0 } })));
    return {};
  },

  async job_save(ctx, { job_id, job, salary }) {
    requireAdmin(ctx);
    job = str(job).trim();
    if (!job) fail("직업을 입력해 주세요.");
    salary = toInt(salary);
    if (salary < 0) fail("월급은 0 이상이어야 합니다.");
    if (job_id) {
      await update("job_salary", job_id, { job, salary, student_count: 0, updated_at: serverTimestamp() });
    } else {
      const rows = await listJobs();
      const order = rows.length ? Math.max(...rows.map((r) => r.order)) + 1 : 1;
      await add("job_salary", { order, job, salary, student_count: 0, assigned_ids: [], created_at: serverTimestamp() });
    }
    return {};
  },

  async job_delete(ctx, { job_id }) {
    requireAdmin(ctx);
    if (!job_id) fail("직업을 선택해 주세요.");
    await del("job_salary", job_id);
    return {};
  },

  async job_reorder(ctx, { ids }) {
    requireAdmin(ctx);
    await batchWrite((ids || []).map((id, i) => ({ type: "update", ref: ref("job_salary", String(id)), data: { order: i + 1 } })));
    return {};
  },

  // 📥 엑셀(순 | 직업 | 월급). wipe면 기존 직업 모두 지우고 새로
  async jobs_bulk_save(ctx, { rows, wipe }) {
    requireAdmin(ctx);
    rows = Array.isArray(rows) ? rows : [];
    if (!rows.length) fail("저장할 행이 없습니다.");
    const old = await listJobs();
    if (wipe) await batchWrite(old.map((r) => ({ type: "delete", ref: ref("job_salary", r._id) })));
    const byName = wipe ? {} : Object.fromEntries(old.map((r) => [r.job, r]));
    for (const r of rows) {
      const job = str(r["직업"]).trim();
      if (!job) continue;
      const payload = { order: toInt(r["순"], 1), job, salary: toInt(r["월급"]), student_count: 0 };
      if (byName[job]) await update("job_salary", byName[job]._id, { ...payload, updated_at: serverTimestamp() });
      else await add("job_salary", { ...payload, assigned_ids: [], created_at: serverTimestamp() });
    }
    return {};
  },
};
