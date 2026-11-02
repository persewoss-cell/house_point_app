// 로그인 / 비밀번호 변경 / 계정 관리(생성·PIN변경·삭제) / 관리자 비밀번호 / 가족 상단 요약
import { add, update, set, serverTimestamp } from "../db.js";
import {
  ADMIN_NAME, ADMIN_AUTH_DOC, fail, pinOk, adminPinOk, isAdminPin, getAdminAuth, hashAdminPin, pinVersion,
  authStudent, findStudentByName, requireLogin, requireStudent, requireAdmin, sha256,
} from "../auth.js";
import { loadRoleLookup, roleNameFor, investSummaryFor, savingsTotalFor, getOne } from "../core.js";
import { str, toInt } from "../../shared/format.js";

const ADMIN_USER = { role: "admin", name: ADMIN_NAME, sid: "", perms: ["admin_all"], invest_enabled: true };

function userInfo(ctx) {
  if (ctx.isAdmin) return ADMIN_USER;
  const s = ctx.student || {};
  return {
    role: "student",
    name: str(s.name),
    sid: ctx.sid,
    perms: [],
    invest_enabled: s.invest_enabled === undefined || s.invest_enabled === null ? true : !!s.invest_enabled,
  };
}

async function adminSession() {
  const a = await getAdminAuth();
  return { role: "admin", pv: String(a.pin_hash).slice(0, 10) };
}

async function setAdminPin(pin) {
  const salt = (await sha256(`${Math.random()}:${Date.now()}`)).slice(0, 16);
  await set(...ADMIN_AUTH_DOC, { salt, pin_hash: await hashAdminPin(pin, salt), updated_at: serverTimestamp() });
}

export default {
  // 관리자 비밀번호를 아직 정하지 않았는지 (처음 한 번 설정 화면)
  async admin_status() {
    const a = await getAdminAuth();
    return { admin_ready: !!(a && a.pin_hash) };
  },

  // 처음 한 번: 관리자 비밀번호 정하기 (이미 정했으면 불가)
  async admin_setup(ctx, { new_pin, new_pin2 }) {
    const a = await getAdminAuth();
    if (a && a.pin_hash) fail("관리자 비밀번호가 이미 설정되어 있어요.");
    new_pin = str(new_pin).trim();
    if (!adminPinOk(new_pin)) fail("관리자 비밀번호는 4자 이상이어야 해요. (길게 정할수록 안전해요)");
    if (new_pin !== str(new_pin2).trim()) fail("비밀번호와 확인이 일치하지 않습니다.");
    await setAdminPin(new_pin);
    return { session: await adminSession(), user: ADMIN_USER };
  },

  async login(ctx, { name, pin }) {
    name = str(name).trim();
    pin = str(pin).trim();
    if (!name) fail("이름을 입력해 주세요.");
    if (name === ADMIN_NAME) {
      const a = await getAdminAuth();
      if (!a || !a.pin_hash) return { need_admin_setup: true };
      if (!(await isAdminPin(pin))) fail("이름 또는 비밀번호가 틀립니다.");
      return { session: await adminSession(), user: ADMIN_USER };
    }
    if (!pinOk(pin)) fail("비밀번호는 4자리 숫자여야 해요.");
    const d = await authStudent(name, pin);
    if (!d) fail("이름 또는 비밀번호가 틀립니다.");
    return { session: { role: "student", sid: String(d._id), pv: await pinVersion(d.pin) }, user: { role: "student", name: str(d.name), sid: String(d._id) } };
  },

  async session(ctx) {
    if (!ctx.role) return { user: null };
    return { user: userInfo(ctx) };
  },

  // 가족 본인 비밀번호 변경 → 이 기기는 로그인 유지(다른 기기는 로그아웃)
  async change_pin_student(ctx, { old_pin, new_pin }) {
    requireStudent(ctx);
    old_pin = str(old_pin).trim();
    new_pin = str(new_pin).trim();
    if (!pinOk(old_pin)) fail("기존 비밀번호는 4자리 숫자여야 합니다.");
    if (!pinOk(new_pin)) fail("새 비밀번호는 4자리 숫자여야 합니다.");
    if (str(ctx.student.pin) !== old_pin) fail("기존 비밀번호가 틀립니다.");
    await update("students", ctx.sid, { pin: new_pin });
    return { session: { role: "student", sid: ctx.sid, pv: await pinVersion(new_pin) } };
  },

  // 관리자: 관리자 비밀번호 변경 → 이 기기는 로그인 유지, 다른 기기의 관리자 로그인은 풀림
  async admin_change_pin(ctx, { old_pin, new_pin, new_pin2 }) {
    requireAdmin(ctx);
    if (!(await isAdminPin(old_pin))) fail("기존 관리자 비밀번호가 틀립니다.");
    new_pin = str(new_pin).trim();
    if (!adminPinOk(new_pin)) fail("새 관리자 비밀번호는 4자 이상이어야 해요.");
    if (new_pin !== str(new_pin2).trim()) fail("새 비밀번호와 확인이 일치하지 않습니다.");
    await setAdminPin(new_pin);
    return { session: await adminSession() };
  },

  // [관리자] 계정 생성 / PIN 변경 / 삭제 (관리자 비밀번호로 한 번 더 확인)
  async sidebar_admin(ctx, { admin_pin, op, name, pin }) {
    requireAdmin(ctx);
    name = str(name).trim();
    pin = str(pin).trim();
    if (!str(admin_pin).trim()) fail("관리자 비밀번호를 입력해 주세요.");
    if (!(await isAdminPin(admin_pin))) fail("관리자 비밀번호가 틀립니다.");
    if (name === ADMIN_NAME) fail(`'${ADMIN_NAME}'는 계정 이름으로 쓸 수 없어요.`);
    if (op === "create") {
      if (!name) fail("이름을 입력해 주세요.");
      if (!pinOk(pin)) fail("비밀번호는 4자리 숫자여야 해요. (예: 0123)");
      if (await findStudentByName(name)) fail("이미 존재하는 계정입니다.");
      await add("students", { name, pin, balance: 0, is_active: true, created_at: serverTimestamp() });
      return {};
    }
    if (op === "pin") {
      if (!name) fail("이름을 입력해 주세요.");
      if (!pinOk(pin)) fail("새 비밀번호는 4자리 숫자여야 해요.");
      const d = await findStudentByName(name);
      if (!d) fail("해당 이름의 계정을 찾지 못했습니다.");
      await update("students", d._id, { pin });
      return {};
    }
    if (op === "delete") {
      if (!name) fail("삭제할 이름(계정)을 입력해 주세요.");
      const d = await findStudentByName(name);
      if (!d) fail("해당 이름의 계정을 찾지 못했습니다.");
      await update("students", d._id, { is_active: false });
      return {};
    }
    fail("잘못된 요청입니다.");
  },

  // 가족 화면 위 요약 (기존 사용자 화면 상단 요약)
  async user_header(ctx) {
    requireLogin(ctx);
    if (ctx.isAdmin) return { header: null };
    const sid = ctx.sid;
    const [s, sv, inv, lookup] = await Promise.all([getOne("students", sid), savingsTotalFor(sid), investSummaryFor(sid), loadRoleLookup()]);
    const bal = toInt(s && s.balance);
    return {
      header: {
        asset_total: bal + sv + toInt(inv.evalTotal),
        balance: bal,
        savings_total: sv,
        inv_principal_total: inv.prinTotal,
        inv_principal_text: inv.prinText,
        inv_eval_total: inv.evalTotal,
        inv_eval_text: inv.evalText,
        role_name: roleNameFor(s, sid, lookup) || "없음",
      },
    };
  },
};
