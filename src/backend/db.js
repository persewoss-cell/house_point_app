// Firestore 공용 도우미 (기존 Streamlit 앱과 같은 컬렉션·필드 구조를 그대로 사용)
import {
  collection, doc, getDoc, getDocs, addDoc, setDoc, updateDoc, deleteDoc, query, where, orderBy, limit as qLimit,
  runTransaction, serverTimestamp, writeBatch,
} from "firebase/firestore";
import { db } from "./firebase.js";

export { serverTimestamp, where, orderBy };
export const qlimit = qLimit;

// 문서 → { ...데이터, _id }
const withId = (snap) => (snap.exists() ? { ...snap.data(), _id: snap.id } : null);

export async function getOne(col, id) {
  if (!id) return null;
  return withId(await getDoc(doc(db(), col, String(id))));
}

// find("students", where("is_active", "==", true), orderBy(...), qlimit(10))
export async function find(col, ...constraints) {
  const snap = await getDocs(constraints.length ? query(collection(db(), col), ...constraints) : collection(db(), col));
  return snap.docs.map((d) => ({ ...d.data(), _id: d.id }));
}

export async function add(col, data) {
  const ref = await addDoc(collection(db(), col), data);
  return ref.id;
}

export async function set(col, id, data, merge = false) {
  await setDoc(doc(db(), col, String(id)), data, { merge });
}

export async function update(col, id, data) {
  await updateDoc(doc(db(), col, String(id)), data);
}

export async function del(col, id) {
  await deleteDoc(doc(db(), col, String(id)));
}

export function ref(col, id) {
  return id ? doc(db(), col, String(id)) : doc(collection(db(), col));
}

export function tx(fn) {
  return runTransaction(db(), fn);
}

// 여러 문서 한 번에 쓰기 (Firestore 한 번 최대 500개 → 나눠서)
export async function batchWrite(ops) {
  for (let i = 0; i < ops.length; i += 450) {
    const b = writeBatch(db());
    for (const op of ops.slice(i, i + 450)) {
      if (op.type === "update") b.update(op.ref, op.data);
      else if (op.type === "set") b.set(op.ref, op.data, { merge: !!op.merge });
      else if (op.type === "delete") b.delete(op.ref);
    }
    await b.commit();
  }
}
