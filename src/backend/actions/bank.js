// 💰입금/출금(관리자) · 📝 통장/거래(가족) : 일괄/개인 입출금, 템플릿, 되돌리기
import { find, add, set, del, where, orderBy, qlimit, batchWrite, ref } from "../db.js";
import { fail, requireLogin, requireAdmin, requireStudent, isAdminPin, ADMIN_NAME } from "../auth.js";
import { applyTx, checkTradeInput, listAccounts, activeStudents, getTxRows, canRemove, removeTx, getOne } from "../core.js";
import { str, toInt, ior, toDate, fmtKrDatetimeNoYear } from "../../shared/format.js";

const newBatchId = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;

export async function listTemplates() {
  const docs = await find("templates");
  const out = [];
  for (const t of docs) {
    if (!t.label) continue;
    out.push({
      template_id: String(t._id),
      label: t.label,
      kind: t.kind,
      amount: toInt(t.amount),
      order: ior(t.order, 999999),
    });
  }
  out.sort((a, b) => a.order - b.order || String(a.label).localeCompare(String(b.label), "ko"));
  return out;
}

// 템플릿: 내역 이름 · 종류 · 금액 · 순서 (기존 앱과 같은 필드)
async function upsertTemplate({ template_id, base_label, kind, amount, order }) {
  const label = str(base_label).trim();
  kind = str(kind).trim();
  amount = toInt(amount);
  order = ior(order, 1);
  if (!label) fail("내역 이름이 필요합니다.");
  if (kind !== "deposit" && kind !== "withdraw") fail("종류는 입금/출금만 가능합니다.");
  if (amount <= 0) fail("금액은 1 이상이어야 합니다.");
  if (order <= 0) fail("순서는 1 이상이어야 합니다.");
  const payload = { label, kind, amount, order };
  if (template_id) await set("templates", template_id, payload, true);
  else await add("templates", payload);
}

// 관리자 기록(되돌리기 목록에 나오는 것): 관리자가 넣은 입금/출금
function isAdminTx(t) {
  const ty = str(t.type);
  if (ty !== "deposit" && ty !== "withdraw") return false;
  const rec = str(t.recorded_by_name || t.recorder);
  return rec === ADMIN_NAME || rec.startsWith(`${ADMIN_NAME}(`);
}

export default {
  async templates_list(ctx) {
    requireLogin(ctx);
    return { templates: await listTemplates() };
  },

  async template_save(ctx, args) {
    requireAdmin(ctx);
    await upsertTemplate(args || {});
    return {};
  },

  async template_delete(ctx, { template_id }) {
    requireAdmin(ctx);
    if (!template_id) fail("template_id가 없습니다.");
    await del("templates", template_id);
    return {};
  },

  // 엑셀 일괄 저장 (delete_old: 기존 템플릿 모두 지우고 덮어쓰기)
  async templates_bulk_save(ctx, { rows, delete_old }) {
    requireAdmin(ctx);
    rows = Array.isArray(rows) ? rows : [];
    if (!rows.length) fail("저장할 행이 없습니다.");
    if (delete_old) {
      const old = await find("templates");
      await batchWrite(old.map((t) => ({ type: "delete", ref: ref("templates", t._id) })));
    }
    let saved = 0;
    for (const r of rows) {
      await upsertTemplate({
        base_label: r["내역이름"],
        kind: str(r["종류"]).trim() === "입금" ? "deposit" : "withdraw",
        amount: r["금액"],
        order: r["순서"],
      });
      saved += 1;
    }
    return { saved };
  },

  // 템플릿 드롭다운 ▲▼ 순서 저장
  async tpl_reorder(ctx, { ids }) {
    requireAdmin(ctx);
    ids = (ids || []).map(String);
    await batchWrite(ids.map((id, i) => ({ type: "update", ref: ref("templates", id), data: { order: i + 1 } })));
    return {};
  },

  async accounts_list(ctx) {
    requireAdmin(ctx);
    return { accounts: await listAccounts() };
  },

  // 전체 일괄 입금/출금 (기존 api_admin_bulk_deposit / _withdraw: 출금은 잔액 부족이어도 적용)
  async bank_bulk(ctx, { memo, dep, wd }) {
    requireAdmin(ctx);
    const t = checkTradeInput(memo, dep, wd);
    const studs = await activeStudents();
    if (!studs.length) fail("활성 계정이 없습니다.");
    const batch_id = newBatchId();
    let count = 0;
    for (const s of studs) {
      await applyTx({ sid: s.student_id, memo: t.memo, amount: t.amount, type: t.type, recorder: ADMIN_NAME, extra: { batch_id, batch_kind: "bulk", source: "bank_admin" } });
      count += 1;
    }
    return { mode: t.type, count };
  },

  // 체크한 가족에게만 입금/출금 (기존 api_admin_add_tx_by_student_id: 출금은 음수 잔액 허용)
  async bank_personal(ctx, { sids, memo, dep, wd }) {
    requireAdmin(ctx);
    const t = checkTradeInput(memo, dep, wd);
    sids = (sids || []).map(String).filter(Boolean);
    if (!sids.length) fail("대상 가족을 1명 이상 선택해 주세요.");
    const batch_id = newBatchId();
    let ok_cnt = 0;
    const failed = [];
    for (const sid of sids) {
      try {
        await applyTx({ sid, memo: t.memo, amount: t.amount, type: t.type, recorder: ADMIN_NAME, extra: { batch_id, batch_kind: "personal", source: "bank_admin" } });
        ok_cnt += 1;
      } catch (e) {
        failed.push(sid);
      }
    }
    if (!ok_cnt) fail("저장 실패");
    return { ok_cnt, failed };
  },

  // 가족 본인 입금/출금 (기존 api_add_tx: 입금은 바로 반영, 출금은 잔액 이내)
  async student_trade(ctx, { memo, dep, wd }) {
    requireStudent(ctx);
    const t = checkTradeInput(memo, dep, wd);
    const r = await applyTx({ sid: ctx.sid, memo: t.memo, amount: t.amount, type: t.type, recorder: ctx.name, checkBalance: true });
    return { mode: t.type, balance: r.balance };
  },

  async tx_list(ctx, { sid, limit }) {
    requireLogin(ctx);
    let target = ctx.sid;
    if (sid && String(sid) !== ctx.sid) {
      requireAdmin(ctx);
      target = String(sid);
    }
    if (!target) fail("계정 정보가 없습니다.");
    return { rows: await getTxRows(target, toInt(limit) || 200) };
  },

  // 되돌리기 목록: 관리자가 넣은 최근 입금/출금 (한 번에 처리한 여러 명은 한 줄로)
  async undo_list(ctx) {
    requireAdmin(ctx);
    const [txs, studs] = await Promise.all([find("transactions", orderBy("created_at", "desc"), qlimit(600)), find("students")]);
    const nm = Object.fromEntries(studs.map((x) => [String(x._id), str(x.name)]));
    const rollbacks = new Set(txs.filter((x) => str(x.type) === "rollback").map((x) => str(x.related_tx)));
    const who = (sid) => nm[sid] || "(삭제된 계정)";
    const groups = new Map();
    const items = [];
    for (const t of txs) {
      if (!isAdminTx(t) || !canRemove(t, rollbacks)) continue;
      if (t.batch_id) {
        let g = groups.get(t.batch_id);
        if (!g) {
          g = { key: `b:${t.batch_id}`, t: toDate(t.created_at), memo: str(t.memo), amount: toInt(t.amount), kind: str(t.batch_kind), sids: [] };
          groups.set(t.batch_id, g);
          items.push(g);
        }
        g.sids.push(str(t.student_id));
      } else {
        items.push({ key: `t:${t._id}`, t: toDate(t.created_at), memo: str(t.memo), amount: toInt(t.amount), kind: "single", sids: [str(t.student_id)] });
      }
      if (items.length > 40) {
        items.pop();
        break;
      }
    }
    const rows = items.map((x) => {
      const target = x.kind === "bulk" ? `전체 ${x.sids.length}명` : x.sids.length > 1 ? `${who(x.sids[0])} 외 ${x.sids.length - 1}명` : who(x.sids[0]);
      const money = x.amount >= 0 ? `입금 ${x.amount}` : `출금 ${-x.amount}`;
      return { key: x.key, label: `${x.t ? fmtKrDatetimeNoYear(x.t) : ""} | ${target} | ${x.memo} | ${money}` };
    });
    return { rows };
  },

  // 되돌리기 실행: 기록을 지우고 잔액을 원래대로 (관리자 비밀번호 필요)
  async undo_apply(ctx, { admin_pin, key }) {
    requireAdmin(ctx);
    if (!(await isAdminPin(admin_pin))) fail("관리자 비밀번호가 틀립니다.");
    key = str(key);
    let txs = [];
    if (key.startsWith("b:")) {
      txs = await find("transactions", where("batch_id", "==", key.slice(2)));
    } else if (key.startsWith("t:")) {
      const t = await getOne("transactions", key.slice(2));
      if (t && isAdminTx(t)) txs = [t];
    }
    if (!txs.length) fail("이미 되돌렸거나 되돌릴 수 없는 기록이에요.");
    let n = 0;
    for (const t of txs) if (await removeTx(t)) n += 1;
    if (!n) fail("이미 되돌린 기록이에요.");
    return { students: n };
  },
};
