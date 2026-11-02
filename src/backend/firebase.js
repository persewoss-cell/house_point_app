// Firebase 연결 (브라우저에서 바로 Firestore 사용)
// - 접속하면 자동으로 "익명 로그인"을 해서, 보안 규칙(로그인한 사람만 읽기/쓰기)을 통과함
import { initializeApp } from "firebase/app";
import { getAuth, signInAnonymously, onAuthStateChanged, connectAuthEmulator } from "firebase/auth";
import { getFirestore, connectFirestoreEmulator } from "firebase/firestore";
import { firebaseConfig as realConfig } from "../firebaseConfig.js";

// 개발용: VITE_USE_EMULATOR=1 로 실행하면 내 컴퓨터의 Firebase 에뮬레이터에 연결 (실제 데이터는 건드리지 않음)
const useEmulator = import.meta.env.VITE_USE_EMULATOR === "1";
const firebaseConfig = useEmulator ? { apiKey: "demo-key", authDomain: "localhost", projectId: "demo-house" } : realConfig;

export const configMissing = !firebaseConfig || !firebaseConfig.apiKey || !firebaseConfig.projectId;

let _db = null;
let _readyPromise = null;

export function ready() {
  if (configMissing) {
    return Promise.reject(new Error("Firebase 설정이 비어 있어요. src/firebaseConfig.js 에 웹 앱 설정값을 넣어 주세요."));
  }
  if (_readyPromise) return _readyPromise;
  _readyPromise = (async () => {
    const app = initializeApp(firebaseConfig);
    const auth = getAuth(app);
    if (useEmulator) connectAuthEmulator(auth, "http://127.0.0.1:9099", { disableWarnings: true });
    await new Promise((resolve, reject) => {
      const off = onAuthStateChanged(auth, async (u) => {
        if (u) {
          off();
          resolve();
          return;
        }
        try {
          await signInAnonymously(auth);
        } catch (e) {
          off();
          reject(new Error(`익명 로그인 실패: ${e.code || e.message} (Firebase 콘솔 → Authentication → 익명 로그인을 켜 주세요)`));
        }
      });
    });
    _db = getFirestore(app);
    if (useEmulator) connectFirestoreEmulator(_db, "127.0.0.1", 8080);
    return _db;
  })();
  _readyPromise.catch(() => {
    _readyPromise = null;
  });
  return _readyPromise;
}

export function db() {
  if (!_db) throw new Error("Firebase가 아직 준비되지 않았어요.");
  return _db;
}
