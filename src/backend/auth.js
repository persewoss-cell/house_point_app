// 로그인 확인 + 관리자 비밀번호(암호화 저장)
// - 관리자 비밀번호는 코드에 적지 않고 Firestore config/admin_auth 에 "해시(암호화된 값)"로만 저장
// - 로그인 정보는 이 기기 브라우저(localStorage)에 저장, 비밀번호가 바뀌면 다른 기기는 자동 로그아웃
import { getOne, find, where } from "./db.js";
import { str } from "../shared/format.js";

export const ADMIN_NAME = "관리자";
export const ADMIN_AUTH_DOC = ["config", "admin_auth"];

export class ApiError extends Error {
  constructor(msg) {
    super(msg);
    this.userMessage = msg;
  }
}

export function fail(msg) {
  throw new ApiError(msg);
}

export async function sha256(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(String(text)));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// 가족 비밀번호: 4자리 숫자 (기존 앱과 같음)
export function pinOk(pin) {
  return /^\d{4}$/.test(String(pin ?? "").trim());
}

// 관리자 비밀번호: 4자리 이상 (길수록 안전)
export function adminPinOk(pin) {
  return String(pin ?? "").trim().length >= 4;
}

export async function getAdminAuth() {
  return await getOne(...ADMIN_AUTH_DOC);
}

export async function hashAdminPin(pin, salt) {
  return await sha256(`house-admin:${salt}:${String(pin).trim()}`);
}

export async function isAdminPin(pin) {
  const a = await getAdminAuth();
  if (!a || !a.pin_hash || !a.salt) return false;
  return (await hashAdminPin(pin, a.salt)) === a.pin_hash;
}

export async function pinVersion(pin) {
  return (await sha256(`pv:${str(pin)}`)).slice(0, 10);
}

// 기존 fs_get_student_doc_by_name / fs_auth_student
export async function findStudentByName(name) {
  const nm = str(name).trim();
  if (!nm) return null;
  const docs = await find("students", where("name", "==", nm), where("is_active", "==", true));
  return docs[0] || null;
}

export async function authStudent(name, pin) {
  const d = await findStudentByName(name);
  if (!d) return null;
  if (str(d.pin) !== str(pin).trim()) return null;
  return d;
}

// 저장된 로그인(세션) 확인: 비밀번호가 바뀌었거나 계정이 삭제됐으면 로그인 풀림
export async function buildCtx(session) {
  const ctx = { role: null, isAdmin: false, sid: "", name: "", student: null, perms: new Set() };
  if (!session || typeof session !== "object") return ctx;
  if (session.role === "admin") {
    const a = await getAdminAuth();
    if (!a || !a.pin_hash || session.pv !== String(a.pin_hash).slice(0, 10)) return ctx;
    ctx.role = "admin";
    ctx.isAdmin = true;
    ctx.name = ADMIN_NAME;
    ctx.perms = new Set(["admin_all"]);
    return ctx;
  }
  if (session.role === "student" && session.sid) {
    const d = await getOne("students", session.sid);
    if (!d || d.is_active !== true) return ctx;
    if (session.pv !== (await pinVersion(d.pin))) return ctx;
    ctx.role = "student";
    ctx.sid = String(d._id);
    ctx.name = str(d.name);
    ctx.student = d;
  }
  return ctx;
}

export function requireLogin(ctx) {
  if (!ctx.role) fail("로그인이 필요합니다.");
}

export function requireAdmin(ctx) {
  if (!ctx.isAdmin) fail("관리자 전용입니다.");
}

export function requireStudent(ctx) {
  if (ctx.role !== "student") fail("가족 계정으로 로그인해 주세요.");
}
