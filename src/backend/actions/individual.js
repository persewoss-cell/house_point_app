// 🔎 개별조회 : 가족별 한 줄 요약 + 통장내역 + 통장내역 삭제
import { find, where } from "../db.js";
import { fail, requireAdmin, isAdminPin } from "../auth.js";
import {
  activeStudents, loadRoleLookup, roleNameFor, loadInvestProductMap, investSummary, canRemove, rolledBackIds, removeTx, getOne,
} from "../core.js";
import { str, toInt } from "../../shared/format.js";

export default {
  async individual_students(ctx) {
    requireAdmin(ctx);
    const rows = (await activeStudents())
      .filter((x) => str(x.name).trim())
      .map((x) => ({ student_id: x.student_id, name: str(x.name).trim(), balance: toInt(x.balance) }));
    rows.sort((a, b) => a.name.localeCompare(b.name, "ko"));
    return { rows };
  },

  // 고른 가족들의 접힘 한 줄 요약
  async individual_summaries(ctx, { sids }) {
    requireAdmin(ctx);
    sids = (sids || []).map(String);
    if (!sids.length) return { rows: [] };
    const [lookup, prodMap] = await Promise.all([loadRoleLookup(), loadInvestProductMap()]);
    const rows = await Promise.all(
      sids.map(async (sid) => {
        const [s, ledger, savings] = await Promise.all([
          getOne("students", sid),
          find("invest_ledger", where("student_id", "==", sid)),
          find("savings", where("student_id", "==", sid)),
        ]);
        const bal = toInt(s && s.balance);
        const sv = savings.reduce((acc, x) => {
          const st = str(x.status || "active").toLowerCase().trim();
          return st === "active" || st === "running" ? acc + toInt(x.principal) : acc;
        }, 0);
        const iv = investSummary(ledger, prodMap);
        return {
          student_id: sid,
          name: str(s && s.name),
          asset_total: bal + sv + toInt(iv.evalTotal),
          balance: bal,
          savings_total: sv,
          inv_text: iv.evalText,
          role_name: roleNameFor(s, sid, lookup),
        };
      })
    );
    return { rows };
  },

  // 체크한 통장내역 완전히 삭제 (잔액·이후 총액 정정)
  async tx_delete(ctx, { admin_pin, sid, tx_ids }) {
    requireAdmin(ctx);
    tx_ids = (tx_ids || []).map(String);
    if (!tx_ids.length) fail("체크된 항목이 없어요.");
    if (!str(admin_pin).trim() || !(await isAdminPin(admin_pin))) fail("관리자 비밀번호(PIN)가 올바르지 않습니다.");
    sid = str(sid);
    if (!sid) fail("삭제할 항목이 없습니다.");
    const rolled = await rolledBackIds(sid);
    const valid = [];
    let blocked = 0;
    for (const id of tx_ids) {
      const t = await getOne("transactions", id);
      if (!t || str(t.student_id) !== sid) continue;
      if (canRemove(t, rolled)) valid.push(t);
      else blocked += 1;
    }
    if (!valid.length) fail("선택한 항목이 모두 삭제 불가합니다. (적금/투자/되돌리기 관련 내역은 삭제할 수 없어요)");
    let deleted = 0;
    const errors = [];
    for (const t of valid) {
      try {
        if (!(await removeTx(t))) throw new Error("이미 삭제됨");
        deleted += 1;
      } catch (e) {
        errors.push(`[삭제실패] ${str(t.memo)}: ${e.message || e}`);
      }
    }
    const message = blocked ? `삭제 제외 ${blocked}건(적금/투자/되돌리기 관련 내역)은 건너뛰었습니다.` : null;
    return { deleted, errors, message };
  },
};
