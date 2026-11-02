// 데이터 처리 입구: 서버 대신 브라우저에서 바로 Firestore를 사용 (src/backend)
// 로그인 정보(세션)는 이 기기 브라우저(localStorage)에 저장 → 새로고침해도 로그인 유지
import { callAction } from "../backend/index.js";

const TOKEN_KEY = "hp_session";

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

export function setToken(t) {
  try {
    if (t) localStorage.setItem(TOKEN_KEY, typeof t === "string" ? t : JSON.stringify(t));
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* 저장 불가 환경 */
  }
}

function readSession() {
  try {
    const raw = getToken();
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

let busyCount = 0;
const busyListeners = new Set();
export function onBusy(fn) {
  busyListeners.add(fn);
  return () => busyListeners.delete(fn);
}
function setBusy(delta) {
  busyCount += delta;
  busyListeners.forEach((f) => f(busyCount > 0));
}

// 로그인이 풀렸을 때(비밀번호 변경·계정 삭제) 알림
const authLostListeners = new Set();
export function onAuthLost(fn) {
  authLostListeners.add(fn);
  return () => authLostListeners.delete(fn);
}

// 결과: { ok: true, ... } 또는 { ok: false, error }
export async function api(action, args = {}) {
  setBusy(1);
  try {
    const r = await callAction(action, args, readSession());
    if (r && r.auth_lost) {
      setToken("");
      authLostListeners.forEach((f) => f());
    }
    return r;
  } catch (e) {
    return { ok: false, error: `오류: ${e.message || e}` };
  } finally {
    setBusy(-1);
  }
}

// 로그인 정보 기억하기 (기존 앱의 ce_saved_name / ce_saved_pin 과 같은 키)
export const remember = {
  read() {
    const r = (k) => {
      try {
        return localStorage.getItem(k) || "";
      } catch {
        return "";
      }
    };
    return {
      name: r("hp_saved_name"),
      pin: r("hp_saved_pin"),
      rememberName: r("hp_remember_name") === "1",
      rememberPin: r("hp_remember_pin") === "1",
    };
  },
  write({ name, pin, rememberName, rememberPin }) {
    const w = (k, v) => {
      try {
        if (v === null) localStorage.removeItem(k);
        else localStorage.setItem(k, v);
      } catch {
        /* ignore */
      }
    };
    if (rememberName && name) {
      w("hp_saved_name", name);
      w("hp_remember_name", "1");
    } else {
      w("hp_saved_name", null);
      w("hp_remember_name", null);
    }
    if (rememberPin && pin) {
      w("hp_saved_pin", pin);
      w("hp_remember_pin", "1");
    } else {
      w("hp_saved_pin", null);
      w("hp_remember_pin", null);
    }
  },
};
