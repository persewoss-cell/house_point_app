// 🎯 목표 (기존 우리집 앱 goals 컬렉션 그대로: student_id, target_amount, goal_date)
import { find, add, update, where, serverTimestamp } from "../db.js";
import { fail, requireLogin, requireStudent, requireAdmin } from "../auth.js";
import { investSummaryFor, getOne } from "../core.js";
import { str, toInt, toDate, kstParts, pad2 } from "../../shared/format.js";

async function latestGoal(sid) {
  const docs = await find("goals", where("student_id", "==", str(sid)));
  docs.sort((a, b) => (toDate(b.created_at) || 0) - (toDate(a.created_at) || 0));
  return docs[0] || null;
}

async function goalData(sid) {
  const [g, s, sv, inv] = await Promise.all([latestGoal(sid), getOne("students", sid), find("savings", where("student_id", "==", str(sid))), investSummaryFor(sid)]);
  const savings = sv
    .filter((x) => str(x.status || "active").toLowerCase().trim() === "active")
    .map((x) => {
      const p = kstParts(x.maturity_date);
      return { principal: toInt(x.principal), interest: toInt(x.interest), maturity_kst: p ? `${p.year}-${pad2(p.month)}-${pad2(p.day)}` : "" };
    });
  return {
    goal_amount: toInt(g && g.target_amount),
    goal_date: str(g && g.goal_date),
    balance: toInt(s && s.balance),
    savings,
    inv_eval_total: toInt(inv.evalTotal),
  };
}

export default {
  async goal_load(ctx) {
    requireLogin(ctx);
    if (!ctx.sid) return { goal_amount: 0, goal_date: "", balance: 0, savings: [], inv_eval_total: 0 };
    return await goalData(ctx.sid);
  },

  async goal_of(ctx, { sid }) {
    requireAdmin(ctx);
    return await goalData(str(sid));
  },

  async goal_save(ctx, { goal_amount, goal_date }) {
    requireStudent(ctx);
    goal_amount = toInt(goal_amount);
    goal_date = str(goal_date).trim();
    if (goal_amount <= 0) fail("목표 금액은 1 이상이어야 합니다.");
    const g = await latestGoal(ctx.sid);
    if (g) await update("goals", g._id, { target_amount: goal_amount, goal_date });
    else await add("goals", { student_id: ctx.sid, title: "목표", target_amount: goal_amount, goal_date, created_at: serverTimestamp() });
    return {};
  },
};
