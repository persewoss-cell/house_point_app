import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta, date

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

# =========================
# 설정
# =========================
APP_TITLE = "우리집 포인트 통장"
st.set_page_config(page_title=APP_TITLE, layout="wide")

KST = timezone(timedelta(hours=9))
ADMIN_PIN = "9999"
ADMIN_NAME = "관리자"

# =========================
# 모바일 UI CSS + 템플릿 정렬(촘촘) CSS
# =========================
st.markdown(
    """
    <style>
    section.main > div:first-child { padding-top: 2.6rem; }
    @media (max-width: 768px) {
        section.main > div:first-child { padding-top: 3.2rem; }
    }
    .block-container { padding-bottom: 2.0rem; }

    /* radio → 버튼처럼 */
    div[role="radiogroup"] > label {
        background: #f3f4f6;
        padding: 6px 10px;
        border-radius: 12px;
        margin-right: 6px;
        margin-bottom: 6px;
        border: 1px solid #ddd;
        font-size: 0.85rem;
    }
    div[role="radiogroup"] > label:has(input:checked) {
        background: #2563eb;
        color: #ffffff;
        border-color: #2563eb;
    }

    [data-testid="stDataFrame"] { overflow-x: auto; }

    /* 앱 제목 */
    .app-title {
        font-weight: 900;
        line-height: 1.18;
        margin: 0.6rem 0 1.0rem 0;
        text-align: left;
        font-size: clamp(1.6rem, 5.2vw, 2.8rem);
        white-space: normal;
        word-break: keep-all;
    }
    @media (max-width: 768px) {
        .app-title { font-size: clamp(2.05rem, 7.9vw, 3.3rem); }
    }

    /* ✅ 전체적으로 줄간격 조금 촘촘하게 */
    p, .stMarkdown { margin-bottom: 0.35rem !important; }
    .stCaptionContainer { margin-top: 0.15rem !important; }

    /* ✅ 템플릿 정렬 표(엑셀 느낌) */
    .tpl-head {
        font-weight: 800;
        padding: 6px 6px;
        border-bottom: 2px solid #ddd;
        margin-bottom: 4px;
    }
    .tpl-cell {
        padding: 4px 6px;
        border-bottom: 1px solid #eee;
        line-height: 1.15;
        font-size: 0.95rem;
    }
    .tpl-label {
        font-weight: 700;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    @media (max-width: 768px){
        .tpl-cell { padding: 6px 6px; font-size: 1.02rem; line-height: 1.18; }
        .tpl-label{ white-space: normal; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow:hidden; }
        .tpl-sub { font-size: 0.92rem; line-height: 1.12; }
    }
    .tpl-sub {
        color:#666;
        font-size: 0.85rem;
        margin-top: 2px;
        line-height: 1.05;
    }

    /* ✅ 버튼(특히 화살표) 작게 + 가운데 */
    div[data-testid="stButton"] > button {
        padding: 0.05rem 0.28rem !important;
        min-height: 1.45rem !important;
        line-height: 1 !important;
        font-size: 0.95rem !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    button[kind="primary"] {
        padding: 0.35rem 0.6rem !important;
        min-height: 2.0rem !important;
    }

    /* ✅ 간단 모드(모바일용) 리스트 */
    .tpl-simple {
        border: 1px solid #eee;
        border-radius: 12px;
        padding: 10px 12px;
        background: #fafafa;
        margin-top: 8px;
    }
    .tpl-simple .item {
        padding: 8px 0;
        border-bottom: 1px dashed #e6e6e6;
    }
    .tpl-simple .item:last-child { border-bottom: none; }
    .tpl-simple .idx { font-weight: 900; margin-right: 8px; }
    .tpl-simple .lab { font-weight: 800; }
    .tpl-simple .meta { color:#666; font-size: 0.92rem; margin-top: 2px; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(f'<div class="app-title">🏦 {APP_TITLE}</div>', unsafe_allow_html=True)

# =========================
# Firestore init
# =========================
@st.cache_resource
def init_firestore():
    firebase_dict = dict(st.secrets["firebase"])
    cred = credentials.Certificate(firebase_dict)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_firestore()

# =========================
# Utils
# =========================
def pin_ok(pin: str) -> bool:
    return str(pin or "").isdigit() and len(str(pin or "")) == 4

def toast(msg: str, icon: str = "✅"):
    if hasattr(st, "toast"):
        st.toast(msg, icon=icon)
    else:
        st.success(msg)

def is_admin_login(name: str, pin: str) -> bool:
    return (str(name or "").strip() == ADMIN_NAME) and (str(pin or "").strip() == ADMIN_PIN)

def is_admin_pin(pin: str) -> bool:
    return str(pin or "").strip() == ADMIN_PIN

def format_kr_datetime(val) -> str:
    if val is None or val == "":
        return ""
    if isinstance(val, datetime):
        dt = val.astimezone(KST) if val.tzinfo else val.replace(tzinfo=KST)
    else:
        s = str(val).strip()
        try:
            if "T" in s and s.endswith("Z"):
                dt = datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(KST)
            else:
                dt = datetime.fromisoformat(s)
                dt = dt.astimezone(KST) if dt.tzinfo else dt.replace(tzinfo=KST)
        except Exception:
            return s

    ampm = "오전" if dt.hour < 12 else "오후"
    hour12 = dt.hour % 12
    hour12 = 12 if hour12 == 0 else hour12
    return f"{dt.year}년 {dt.month:02d}월 {dt.day:02d}일 {ampm} {hour12:02d}시 {dt.minute:02d}분"

def _to_utc_datetime(ts):
    if ts is None or ts == "":
        return None
    if isinstance(ts, datetime):
        return ts.astimezone(timezone.utc) if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    if hasattr(ts, "to_datetime"):
        dt = ts.to_datetime()
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    try:
        s = str(ts).strip()
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None

def rate_by_weeks(weeks: int) -> float:
    return weeks * 0.05

def clamp01(x: float) -> float:
    try:
        if x is None or x != x:
            return 0.0
        return max(0.0, min(1.0, float(x)))
    except Exception:
        return 0.0

def _is_savings_memo(memo: str) -> bool:
    memo = str(memo or "")
    return ("적금 가입" in memo) or ("적금 해지" in memo) or ("적금 만기" in memo)

def render_asset_summary(balance_now: int, savings_list: list[dict]):
    sv_total = sum(
        int(s.get("principal", 0) or 0)
        for s in (savings_list or [])
        if str(s.get("status", "")).lower().strip() == "active"
    )
    asset_total = int(balance_now) + int(sv_total)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("내 자산", f"{asset_total}")
    with c2:
        st.metric("통장 잔액", f"{int(balance_now)}")
    with c3:
        st.metric("적금 총액", f"{int(sv_total)}")

def savings_active_total(savings_list: list[dict]) -> int:
    return sum(int(s.get("principal", 0) or 0) for s in savings_list if str(s.get("status", "")).lower() == "active")

# =========================
# Firestore helpers
# =========================
def fs_get_student_doc_by_name(name: str):
    name = (name or "").strip()
    if not name:
        return None
    q = (
        db.collection("students")
        .where(filter=FieldFilter("name", "==", name))
        .where(filter=FieldFilter("is_active", "==", True))
        .limit(1)
        .stream()
    )
    docs = list(q)
    return docs[0] if docs else None

def fs_auth_student(name: str, pin: str):
    doc = fs_get_student_doc_by_name(name)
    if not doc:
        return None
    data = doc.to_dict() or {}
    if str(data.get("pin", "")) != str(pin):
        return None
    return doc

# =========================
# Cached lists
# =========================
@st.cache_data(ttl=30, show_spinner=False)
def api_list_accounts_cached():
    docs = db.collection("students").where(filter=FieldFilter("is_active", "==", True)).stream()
    items = []
    for d in docs:
        s = d.to_dict() or {}
        nm = s.get("name", "")
        if nm:
            items.append({
                "student_id": d.id,
                "name": nm,
                "balance": int(s.get("balance", 0) or 0)
            })
    items.sort(key=lambda x: x["name"])
    return {"ok": True, "accounts": items}

@st.cache_data(ttl=300, show_spinner=False)
def api_list_templates_cached():
    docs = db.collection("templates").stream()
    templates = []
    for d in docs:
        t = d.to_dict() or {}
        if t.get("label"):
            templates.append({
                "template_id": d.id,
                "label": t.get("label"),
                "kind": t.get("kind"),
                "amount": int(t.get("amount", 0) or 0),
                "order": int(t.get("order", 999999) or 999999),
            })
    templates.sort(key=lambda x: (int(x.get("order", 999999)), str(x.get("label", ""))))
    return {"ok": True, "templates": templates}

# =========================
# Account CRUD
# =========================
def api_create_account(name, pin):
    name = (name or "").strip()
    pin = (pin or "").strip()
    if not name:
        return {"ok": False, "error": "이름이 필요합니다."}
    if not (pin.isdigit() and len(pin) == 4):
        return {"ok": False, "error": "PIN은 4자리 숫자여야 합니다."}
    if fs_get_student_doc_by_name(name):
        return {"ok": False, "error": "이미 존재하는 계정입니다."}
    db.collection("students").document().set({
        "name": name,
        "pin": pin,
        "balance": 0,
        "is_active": True,
        "created_at": firestore.SERVER_TIMESTAMP
    })
    api_list_accounts_cached.clear()
    return {"ok": True}

def api_delete_account(name, pin):
    doc = fs_auth_student(name, pin)
    if not doc:
        return {"ok": False, "error": "이름 또는 비밀번호가 틀립니다."}
    db.collection("students").document(doc.id).update({"is_active": False})
    api_list_accounts_cached.clear()
    return {"ok": True}

# =========================
# Transactions
# =========================
def api_add_tx(name, pin, memo, deposit, withdraw):
    memo = (memo or "").strip()
    deposit = int(deposit or 0)
    withdraw = int(withdraw or 0)

    if not memo:
        return {"ok": False, "error": "내역이 필요합니다."}
    if (deposit > 0 and withdraw > 0) or (deposit == 0 and withdraw == 0):
        return {"ok": False, "error": "입금/출금 중 하나만 입력하세요."}

    student_doc = fs_auth_student(name, pin)
    if not student_doc:
        return {"ok": False, "error": "이름 또는 비밀번호가 틀립니다."}

    student_ref = db.collection("students").document(student_doc.id)
    tx_ref = db.collection("transactions").document()

    amount = deposit if deposit > 0 else -withdraw
    tx_type = "deposit" if deposit > 0 else "withdraw"

    @firestore.transactional
    def _do(transaction):
        snap = student_ref.get(transaction=transaction)
        bal = int((snap.to_dict() or {}).get("balance", 0))

        # ✅ 일반 사용자 출금은 잔액 부족이면 불가
        if tx_type == "withdraw" and bal < withdraw:
            raise ValueError("잔액보다 큰 출금은 불가합니다.")

        new_bal = bal + amount
        transaction.update(student_ref, {"balance": new_bal})
        transaction.set(tx_ref, {
            "student_id": student_doc.id,
            "type": tx_type,
            "amount": amount,
            "balance_after": new_bal,
            "memo": memo,
            "created_at": firestore.SERVER_TIMESTAMP
        })
        return new_bal

    try:
        new_bal = _do(db.transaction())
        return {"ok": True, "balance": new_bal}
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"저장 실패: {e}"}

def api_admin_add_tx_by_student_id(admin_pin: str, student_id: str, memo: str, deposit: int, withdraw: int):
    """
    ✅ 관리자 전용: 개별 학생에게 입금/출금
    - 학생 PIN 불필요
    - 출금은 잔액 부족이어도 적용(음수 허용)
    """
    if not is_admin_pin(admin_pin):
        return {"ok": False, "error": "관리자 PIN이 틀립니다."}

    memo = (memo or "").strip()
    deposit = int(deposit or 0)
    withdraw = int(withdraw or 0)

    if not memo:
        return {"ok": False, "error": "내역이 필요합니다."}
    if (deposit > 0 and withdraw > 0) or (deposit == 0 and withdraw == 0):
        return {"ok": False, "error": "입금/출금 중 하나만 입력하세요."}
    if not student_id:
        return {"ok": False, "error": "student_id가 없습니다."}

    student_ref = db.collection("students").document(student_id)
    tx_ref = db.collection("transactions").document()

    amount = deposit if deposit > 0 else -withdraw
    tx_type = "deposit" if deposit > 0 else "withdraw"

    @firestore.transactional
    def _do(transaction):
        snap = student_ref.get(transaction=transaction)
        if not snap.exists:
            raise ValueError("계정을 찾지 못했습니다.")
        bal = int((snap.to_dict() or {}).get("balance", 0))

        new_bal = bal + amount  # ✅ 음수 허용
        transaction.update(student_ref, {"balance": new_bal})
        transaction.set(tx_ref, {
            "student_id": student_id,
            "type": tx_type,
            "amount": amount,
            "balance_after": new_bal,
            "memo": memo,
            "created_at": firestore.SERVER_TIMESTAMP
        })
        return new_bal

    try:
        new_bal = _do(db.transaction())
        return {"ok": True, "balance": new_bal}
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"저장 실패: {e}"}

def api_get_txs_by_student_id(student_id: str, limit=200):
    if not student_id:
        return {"ok": False, "error": "student_id가 없습니다."}

    q = (
        db.collection("transactions")
        .where(filter=FieldFilter("student_id", "==", student_id))
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(int(limit))
        .stream()
    )

    rows = []
    for d in q:
        tx = d.to_dict() or {}
        created_dt_utc = _to_utc_datetime(tx.get("created_at"))
        amt = int(tx.get("amount", 0) or 0)
        rows.append({
            "tx_id": d.id,
            "created_at_utc": created_dt_utc,
            "created_at_kr": format_kr_datetime(created_dt_utc.astimezone(KST)) if created_dt_utc else "",
            "memo": tx.get("memo", ""),
            "type": tx.get("type", ""),
            "amount": amt,
            "deposit": amt if amt > 0 else 0,
            "withdraw": -amt if amt < 0 else 0,
            "balance_after": int(tx.get("balance_after", 0) or 0),
        })

    return {"ok": True, "rows": rows}

def api_get_balance(name, pin):
    student_doc = fs_auth_student(name, pin)
    if not student_doc:
        return {"ok": False, "error": "이름 또는 비밀번호가 틀립니다."}
    data = student_doc.to_dict() or {}
    return {"ok": True, "balance": int(data.get("balance", 0) or 0), "student_id": student_doc.id}

# =========================
# Admin rollback
# =========================
def _already_rolled_back(student_id: str, tx_id: str) -> bool:
    q = (
        db.collection("transactions")
        .where(filter=FieldFilter("student_id", "==", student_id))
        .where(filter=FieldFilter("type", "==", "rollback"))
        .where(filter=FieldFilter("related_tx", "==", tx_id))
        .limit(1)
        .stream()
    )
    return len(list(q)) > 0

def api_admin_rollback_selected(admin_pin: str, student_id: str, tx_ids: list[str]):
    if not is_admin_pin(admin_pin):
        return {"ok": False, "error": "관리자 PIN이 틀립니다."}
    if not student_id or not tx_ids:
        return {"ok": False, "error": "되돌릴 항목이 없습니다."}

    student_ref = db.collection("students").document(student_id)

    tx_docs = []
    for tid in tx_ids:
        snap = db.collection("transactions").document(tid).get()
        if not snap.exists:
            continue
        tx = snap.to_dict() or {}
        if tx.get("student_id") != student_id:
            continue
        tx_docs.append((tid, tx))

    if not tx_docs:
        return {"ok": False, "error": "유효한 거래를 찾지 못했습니다."}

    blocked, valid = [], []
    for tid, tx in tx_docs:
        ttype = str(tx.get("type", "") or "")
        memo = str(tx.get("memo", "") or "")
        if ttype == "rollback":
            blocked.append((tid, "이미 되돌리기 기록"))
            continue
        if _is_savings_memo(memo) or ttype in ("maturity",):
            blocked.append((tid, "적금 관련 내역"))
            continue
        if _already_rolled_back(student_id, tid):
            blocked.append((tid, "이미 되돌린 거래"))
            continue
        valid.append((tid, tx))

    if not valid:
        return {"ok": False, "error": "선택한 항목이 모두 되돌리기 불가합니다. (적금/이미 되돌림 등)"}

    def _tx_time(tx):
        dt = _to_utc_datetime(tx.get("created_at"))
        return dt or datetime(1970, 1, 1, tzinfo=timezone.utc)

    valid.sort(key=lambda x: _tx_time(x[1]))

    undone, total_delta = 0, 0
    for tid, tx in valid:
        amount = int(tx.get("amount", 0) or 0)
        rollback_amount = -amount
        rollback_ref = db.collection("transactions").document()

        @firestore.transactional
        def _do_one(transaction):
            st_snap = student_ref.get(transaction=transaction)
            bal = int((st_snap.to_dict() or {}).get("balance", 0))
            new_bal = bal + rollback_amount
            transaction.update(student_ref, {"balance": new_bal})
            transaction.set(rollback_ref, {
                "student_id": student_id,
                "type": "rollback",
                "amount": rollback_amount,
                "balance_after": new_bal,
                "memo": f"{tid} 되돌리기",
                "related_tx": tid,
                "created_at": firestore.SERVER_TIMESTAMP,
            })
            return new_bal

        _do_one(db.transaction())
        undone += 1
        total_delta += rollback_amount

    info_msg = None
    if blocked:
        info_msg = f"되돌리기 제외 {len(blocked)}건(적금/이미 되돌림 등)은 건너뛰었습니다."

    return {"ok": True, "undone": undone, "delta": total_delta, "message": info_msg}

# =========================
# Savings
# =========================
def api_savings_list_by_student_id(student_id: str):
    docs = (
        db.collection("savings")
        .where(filter=FieldFilter("student_id", "==", student_id))
        .order_by("start_date", direction=firestore.Query.DESCENDING)
        .limit(50)
        .stream()
    )
    out = []
    for d in docs:
        s = d.to_dict() or {}
        out.append({
            "savings_id": d.id,
            "principal": int(s.get("principal", 0) or 0),
            "weeks": int(s.get("weeks", 0) or 0),
            "interest": int(s.get("interest", 0) or 0),
            "maturity_date": _to_utc_datetime(s.get("maturity_date")),
            "status": s.get("status", "active")
        })
    return {"ok": True, "savings": out}

def api_savings_list(name, pin):
    student_doc = fs_auth_student(name, pin)
    if not student_doc:
        return {"ok": False, "error": "이름 또는 비밀번호가 틀립니다."}
    return api_savings_list_by_student_id(student_doc.id)

def api_savings_create(name, pin, principal, weeks):
    principal = int(principal or 0)
    weeks = int(weeks or 0)

    student_doc = fs_auth_student(name, pin)
    if not student_doc:
        return {"ok": False, "error": "이름 또는 비밀번호가 틀립니다."}

    if principal <= 0:
        return {"ok": False, "error": "원금은 1 이상이어야 합니다."}
    if principal % 10 != 0:
        return {"ok": False, "error": "원금은 10단위만 가능합니다."}
    if weeks < 1 or weeks > 10:
        return {"ok": False, "error": "기간은 1~10주만 가능합니다."}

    student_ref = db.collection("students").document(student_doc.id)
    savings_ref = db.collection("savings").document()

    r = rate_by_weeks(weeks)
    interest = round(principal * r)
    maturity_date = datetime.now(timezone.utc) + timedelta(days=weeks * 7)

    @firestore.transactional
    def _do(transaction):
        snap = student_ref.get(transaction=transaction)
        bal = int((snap.to_dict() or {}).get("balance", 0))
        if principal > bal:
            raise ValueError("잔액보다 큰 원금은 가입할 수 없습니다.")

        new_bal = bal - principal
        transaction.update(student_ref, {"balance": new_bal})

        tx_ref = db.collection("transactions").document()
        transaction.set(tx_ref, {
            "student_id": student_doc.id,
            "type": "withdraw",
            "amount": -principal,
            "balance_after": new_bal,
            "memo": f"적금 가입({weeks}주)",
            "created_at": firestore.SERVER_TIMESTAMP
        })

        transaction.set(savings_ref, {
            "student_id": student_doc.id,
            "principal": principal,
            "weeks": weeks,
            "interest": interest,
            "start_date": firestore.SERVER_TIMESTAMP,
            "maturity_date": maturity_date,
            "status": "active"
        })
        return interest, maturity_date

    try:
        interest2, maturity_dt = _do(db.transaction())
        return {"ok": True, "interest": interest2, "maturity_datetime": maturity_dt}
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"적금 가입 실패: {e}"}

def api_savings_cancel(name, pin, savings_id):
    student_doc = fs_auth_student(name, pin)
    if not student_doc:
        return {"ok": False, "error": "이름 또는 비밀번호가 틀립니다."}

    savings_id = str(savings_id or "").strip()
    if not savings_id:
        return {"ok": False, "error": "savings_id가 필요합니다."}

    student_ref = db.collection("students").document(student_doc.id)
    savings_ref = db.collection("savings").document(savings_id)

    @firestore.transactional
    def _do(transaction):
        s_snap = savings_ref.get(transaction=transaction)
        if not s_snap.exists:
            raise ValueError("해당 적금을 찾지 못했습니다.")
        s = s_snap.to_dict() or {}
        if s.get("student_id") != student_doc.id:
            raise ValueError("권한이 없습니다.")
        if s.get("status") != "active":
            raise ValueError("이미 처리된 적금입니다.")

        principal = int(s.get("principal", 0) or 0)
        weeks = int(s.get("weeks", 0) or 0)

        st_snap = student_ref.get(transaction=transaction)
        bal = int((st_snap.to_dict() or {}).get("balance", 0))
        new_bal = bal + principal

        transaction.update(savings_ref, {"status": "canceled"})
        transaction.update(student_ref, {"balance": new_bal})

        tx_ref = db.collection("transactions").document()
        transaction.set(tx_ref, {
            "student_id": student_doc.id,
            "type": "deposit",
            "amount": principal,
            "balance_after": new_bal,
            "memo": f"적금 해지({weeks}주)",
            "created_at": firestore.SERVER_TIMESTAMP
        })
        return principal

    try:
        refunded = _do(db.transaction())
        return {"ok": True, "refunded": refunded}
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"해지 실패: {e}"}

def api_process_maturities(name, pin):
    student_doc = fs_auth_student(name, pin)
    if not student_doc:
        return {"ok": False, "error": "이름 또는 비밀번호가 틀립니다."}

    student_ref = db.collection("students").document(student_doc.id)
    now = datetime.now(timezone.utc)

    q = (
        db.collection("savings")
        .where(filter=FieldFilter("student_id", "==", student_doc.id))
        .where(filter=FieldFilter("status", "==", "active"))
        .stream()
    )

    matured = []
    for d in q:
        s = d.to_dict() or {}
        m_dt = _to_utc_datetime(s.get("maturity_date"))
        if m_dt and m_dt <= now:
            matured.append((d.id, s))

    if not matured:
        return {"ok": True, "matured_count": 0, "paid_total": 0}

    matured_count, paid_total = 0, 0
    for sid, s in matured:
        principal = int(s.get("principal", 0) or 0)
        interest = int(s.get("interest", 0) or 0)
        amount = principal + interest
        weeks = int(s.get("weeks", 0) or 0)

        savings_ref = db.collection("savings").document(sid)
        tx_ref = db.collection("transactions").document()

        @firestore.transactional
        def _do_one(transaction):
            st_snap = student_ref.get(transaction=transaction)
            bal = int((st_snap.to_dict() or {}).get("balance", 0))
            new_bal = bal + amount

            transaction.update(student_ref, {"balance": new_bal})
            transaction.update(savings_ref, {"status": "matured"})
            transaction.set(tx_ref, {
                "student_id": student_doc.id,
                "type": "maturity",
                "amount": amount,
                "balance_after": new_bal,
                "memo": f"적금 만기({weeks}주)",
                "created_at": firestore.SERVER_TIMESTAMP
            })
            return new_bal

        _do_one(db.transaction())
        matured_count += 1
        paid_total += amount

    return {"ok": True, "matured_count": matured_count, "paid_total": paid_total}

# =========================
# Goal
# =========================
def api_get_goal(name, pin):
    student_doc = fs_auth_student(name, pin)
    if not student_doc:
        return {"ok": False, "error": "이름 또는 비밀번호가 틀립니다."}
    return api_get_goal_by_student_id(student_doc.id)

def api_get_goal_by_student_id(student_id: str):
    if not student_id:
        return {"ok": False, "error": "student_id가 없습니다."}

    q = (
        db.collection("goals")
        .where(filter=FieldFilter("student_id", "==", student_id))
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(1)
        .stream()
    )
    docs = list(q)
    if not docs:
        return {"ok": True, "goal_amount": 0, "goal_date": ""}

    g = docs[0].to_dict() or {}
    return {
        "ok": True,
        "goal_amount": int(g.get("target_amount", 0) or 0),
        "goal_date": str(g.get("goal_date", "") or "")
    }

def api_set_goal(name, pin, goal_amount, goal_date_str):
    goal_amount = int(goal_amount or 0)
    goal_date_str = str(goal_date_str or "").strip()

    student_doc = fs_auth_student(name, pin)
    if not student_doc:
        return {"ok": False, "error": "이름 또는 비밀번호가 틀립니다."}
    if goal_amount <= 0:
        return {"ok": False, "error": "목표 금액은 1 이상이어야 합니다."}

    q = (
        db.collection("goals")
        .where(filter=FieldFilter("student_id", "==", student_doc.id))
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(1)
        .stream()
    )
    docs = list(q)
    if docs:
        db.collection("goals").document(docs[0].id).update({
            "target_amount": goal_amount,
            "goal_date": goal_date_str
        })
    else:
        db.collection("goals").document().set({
            "student_id": student_doc.id,
            "title": "목표",
            "target_amount": goal_amount,
            "goal_date": goal_date_str,
            "created_at": firestore.SERVER_TIMESTAMP
        })
    return {"ok": True}

# =========================
# Admin functions
# =========================
def api_admin_reset_pin(admin_pin, name, new_pin):
    if not is_admin_pin(admin_pin):
        return {"ok": False, "error": "관리자 PIN이 틀립니다."}
    if not (str(new_pin).isdigit() and len(str(new_pin)) == 4):
        return {"ok": False, "error": "새 PIN은 4자리 숫자여야 합니다."}

    doc = fs_get_student_doc_by_name(name)
    if not doc:
        return {"ok": False, "error": "계정을 찾지 못했습니다."}
    db.collection("students").document(doc.id).update({"pin": str(new_pin)})
    return {"ok": True}

def api_admin_bulk_deposit(admin_pin, amount, memo):
    if not is_admin_pin(admin_pin):
        return {"ok": False, "error": "관리자 PIN이 틀립니다."}
    amount = int(amount or 0)
    memo = (memo or "").strip() or "일괄 지급"
    if amount <= 0:
        return {"ok": False, "error": "금액은 1 이상이어야 합니다."}

    docs = list(db.collection("students").where(filter=FieldFilter("is_active", "==", True)).stream())
    count = 0
    for d in docs:
        student_id = d.id
        student_ref = db.collection("students").document(student_id)
        tx_ref = db.collection("transactions").document()

        @firestore.transactional
        def _do(transaction):
            snap = student_ref.get(transaction=transaction)
            bal = int((snap.to_dict() or {}).get("balance", 0))
            new_bal = bal + amount
            transaction.update(student_ref, {"balance": new_bal})
            transaction.set(tx_ref, {
                "student_id": student_id,
                "type": "deposit",
                "amount": amount,
                "balance_after": new_bal,
                "memo": memo,
                "created_at": firestore.SERVER_TIMESTAMP
            })

        _do(db.transaction())
        count += 1

    return {"ok": True, "count": count}

def api_admin_bulk_withdraw(admin_pin, amount, memo):
    # ✅ 잔액 부족이어도 적용(음수 허용)
    if not is_admin_pin(admin_pin):
        return {"ok": False, "error": "관리자 PIN이 틀립니다."}
    amount = int(amount or 0)
    memo = (memo or "").strip() or "일괄 벌금"
    if amount <= 0:
        return {"ok": False, "error": "금액은 1 이상이어야 합니다."}

    docs = list(db.collection("students").where(filter=FieldFilter("is_active", "==", True)).stream())
    count = 0
    for d in docs:
        student_id = d.id
        student_ref = db.collection("students").document(student_id)
        tx_ref = db.collection("transactions").document()

        @firestore.transactional
        def _do(transaction):
            snap = student_ref.get(transaction=transaction)
            bal = int((snap.to_dict() or {}).get("balance", 0))
            new_bal = bal - amount
            transaction.update(student_ref, {"balance": new_bal})
            transaction.set(tx_ref, {
                "student_id": student_id,
                "type": "withdraw",
                "amount": -amount,
                "balance_after": new_bal,
                "memo": memo,
                "created_at": firestore.SERVER_TIMESTAMP
            })

        _do(db.transaction())
        count += 1

    return {"ok": True, "count": count}

def api_admin_upsert_template(admin_pin, template_id, label, kind, amount, order):
    if not is_admin_pin(admin_pin):
        return {"ok": False, "error": "관리자 PIN이 틀립니다."}
    label = (label or "").strip()
    kind = (kind or "").strip()
    amount = int(amount or 0)
    order = int(order or 1)

    if not label:
        return {"ok": False, "error": "내역(label)이 필요합니다."}
    if kind not in ("deposit", "withdraw"):
        return {"ok": False, "error": "종류는 deposit/withdraw만 가능합니다."}
    if amount <= 0:
        return {"ok": False, "error": "금액은 1 이상이어야 합니다."}
    if order <= 0:
        return {"ok": False, "error": "순서는 1 이상이어야 합니다."}

    payload = {"label": label, "kind": kind, "amount": amount, "order": order}
    if template_id:
        db.collection("templates").document(template_id).set(payload, merge=True)
    else:
        db.collection("templates").document().set(payload)

    api_list_templates_cached.clear()
    return {"ok": True}

def api_admin_delete_template(admin_pin, template_id):
    if not is_admin_pin(admin_pin):
        return {"ok": False, "error": "관리자 PIN이 틀립니다."}
    template_id = (template_id or "").strip()
    if not template_id:
        return {"ok": False, "error": "template_id가 필요합니다."}
    db.collection("templates").document(template_id).delete()
    api_list_templates_cached.clear()
    return {"ok": True}

def api_admin_backfill_template_order(admin_pin: str):
    if not is_admin_pin(admin_pin):
        return {"ok": False, "error": "관리자 PIN이 틀립니다."}

    docs = list(db.collection("templates").stream())
    items = []
    for d in docs:
        t = d.to_dict() or {}
        if t.get("label"):
            items.append((d.id, t))

    items.sort(key=lambda x: str((x[1] or {}).get("label", "")))

    batch = db.batch()
    for idx, (doc_id, t) in enumerate(items, start=1):
        ref = db.collection("templates").document(doc_id)
        if (t or {}).get("order", None) is None:
            batch.set(ref, {"order": idx}, merge=True)
    batch.commit()

    api_list_templates_cached.clear()
    return {"ok": True, "count": len(items)}

def api_admin_normalize_template_order(admin_pin: str):
    if not is_admin_pin(admin_pin):
        return {"ok": False, "error": "관리자 PIN이 틀립니다."}

    docs = list(db.collection("templates").stream())
    items = []
    for d in docs:
        t = d.to_dict() or {}
        if t.get("label"):
            items.append((d.id, t))

    items.sort(
        key=lambda x: (
            int((x[1] or {}).get("order", 999999) or 999999),
            str((x[1] or {}).get("label", ""))
        )
    )

    batch = db.batch()
    for idx, (doc_id, _) in enumerate(items, start=1):
        ref = db.collection("templates").document(doc_id)
        batch.set(ref, {"order": idx}, merge=True)
    batch.commit()

    api_list_templates_cached.clear()
    return {"ok": True, "count": len(items)}

def api_admin_save_template_orders(admin_pin: str, ordered_template_ids: list[str]):
    if not is_admin_pin(admin_pin):
        return {"ok": False, "error": "관리자 PIN이 틀립니다."}
    if not ordered_template_ids:
        return {"ok": False, "error": "저장할 순서가 없습니다."}

    try:
        batch = db.batch()
        for idx, tid in enumerate(ordered_template_ids, start=1):
            ref = db.collection("templates").document(str(tid))
            batch.set(ref, {"order": idx}, merge=True)
        batch.commit()

        api_list_templates_cached.clear()
        return {"ok": True, "count": len(ordered_template_ids)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# =========================
# Session init
# =========================
defaults = {
    "logged_in": False,
    "admin_ok": False,
    "login_name": "",
    "login_pin": "",
    "data": {},
    "last_maturity_check": {},
    "delete_confirm": False,
    "bulk_confirm": False,
    "bulk_w_confirm": False,
    "tpl_sort_mode": False,
    "tpl_work_ids": [],
    "tpl_mobile_sort_ui": False,
    "tpl_sort_panel_open": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =========================
# UI helpers
# =========================
def refresh_account_data(name: str, pin: str, force: bool = False):
    now = datetime.now(KST)
    slot = st.session_state.data.get(name, {})
    last_ts = slot.get("ts")
    if (not force) and last_ts and (now - last_ts).total_seconds() < 2:
        return

    bal_res = api_get_balance(name, pin)
    if not bal_res.get("ok"):
        st.session_state.data[name] = {"error": bal_res.get("error", "잔액 로드 실패"), "ts": now}
        return

    balance = int(bal_res["balance"])
    student_id = bal_res.get("student_id")

    tx_res = api_get_txs_by_student_id(student_id, limit=300)
    if not tx_res.get("ok"):
        st.session_state.data[name] = {"error": tx_res.get("error", "내역 로드 실패"), "ts": now}
        return

    df_tx = pd.DataFrame(tx_res["rows"])
    if not df_tx.empty:
        df_tx = df_tx.sort_values("created_at_utc", ascending=False)

    sres = api_savings_list(name, pin)
    savings = sres.get("savings", []) if isinstance(sres, dict) and sres.get("ok") else []

    gres = api_get_goal(name, pin)
    goal = gres if isinstance(gres, dict) and gres.get("ok") else {"ok": False, "error": "목표 로드 실패"}

    st.session_state.data[name] = {
        "df_tx": df_tx,
        "balance": balance,
        "savings": savings,
        "goal": goal,
        "student_id": student_id,
        "ts": now
    }

def maybe_check_maturities(name: str, pin: str):
    now = datetime.now(KST)
    last = st.session_state.last_maturity_check.get(name)
    if last and (now - last).total_seconds() < 120:
        return None
    st.session_state.last_maturity_check[name] = now
    return api_process_maturities(name, pin)

def render_tx_table(df_tx: pd.DataFrame):
    if df_tx is None or df_tx.empty:
        st.info("거래 내역이 없어요.")
        return
    view = df_tx.rename(columns={
        "created_at_kr": "날짜-시간",
        "memo": "내역",
        "deposit": "입금",
        "withdraw": "출금",
        "balance_after": "총액"
    })
    st.dataframe(
        view[["내역", "입금", "출금", "총액", "날짜-시간"]],
        use_container_width=True,
        hide_index=True
    )

def render_active_savings_list(savings: list[dict], name: str, pin: str):
    active = [s for s in savings if str(s.get("status", "")).lower() == "active"]
    matured = [s for s in savings if str(s.get("status", "")).lower() == "matured"]
    canceled = [s for s in savings if str(s.get("status", "")).lower() == "canceled"]

    st.markdown("### 🟢 진행 중 적금")
    if not active:
        st.caption("진행 중인 적금이 없어요.")
    else:
        for s in active:
            sid = s["savings_id"]
            principal = int(s["principal"])
            weeks = int(s["weeks"])
            interest2 = int(s["interest"])
            mdt = s.get("maturity_date")
            mkr = format_kr_datetime(mdt.astimezone(KST)) if isinstance(mdt, datetime) else ""
            st.write(f"- 원금 **{principal}**, 기간 **{weeks}주**, 만기일 **{mkr}**, 만기 이자 **{interest2}**")

            if st.button("해지", key=f"sv_cancel_btn_{name}_{sid}", use_container_width=True):
                st.session_state[f"sv_cancel_confirm_{sid}"] = True

            if st.session_state.get(f"sv_cancel_confirm_{sid}", False):
                st.warning("정말로 해지하시겠습니까? (원금만 반환)")
                y, n = st.columns(2)
                with y:
                    if st.button("예", key=f"sv_cancel_yes_{name}_{sid}", use_container_width=True):
                        res = api_savings_cancel(name, pin, sid)
                        if res.get("ok"):
                            toast(f"해지 완료! (+{res.get('refunded', 0)})", icon="🧾")
                            st.session_state[f"sv_cancel_confirm_{sid}"] = False
                            refresh_account_data(name, pin, force=True)
                            st.rerun()
                        else:
                            st.error(res.get("error", "해지 실패"))
                with n:
                    if st.button("아니오", key=f"sv_cancel_no_{name}_{sid}", use_container_width=True):
                        st.session_state[f"sv_cancel_confirm_{sid}"] = False
                        st.rerun()

    if matured:
        st.markdown("### 🔵 만기(자동 반환 완료)")
        for s in matured[:10]:
            st.write(f"- 원금 {int(s['principal'])}, {int(s['weeks'])}주, 이자 {int(s['interest'])}")

    if canceled:
        st.markdown("### ⚪ 해지 기록")
        for s in canceled[:10]:
            st.write(f"- 원금 {int(s['principal'])}, {int(s['weeks'])}주")

def render_goal_section(name: str, pin: str, balance: int, savings_list: list[dict]):
    st.markdown("### 🎯 목표 저금(목표 설정/달성률)")

    goal = st.session_state.data.get(name, {}).get("goal", {"ok": False})
    if not goal.get("ok"):
        st.error(goal.get("error", "목표 정보를 불러오지 못했어요."))
        return

    cur_goal_amt = int(goal.get("goal_amount", 0) or 0)
    cur_goal_date = str(goal.get("goal_date", "") or "")

    c1, c2 = st.columns(2)
    with c1:
        g_amt = st.number_input(
            "목표 금액",
            min_value=1,
            step=1,
            value=cur_goal_amt if cur_goal_amt > 0 else 100,
            key=f"goal_amt_{name}",
        )
    with c2:
        default_date = date.today() + timedelta(days=30)
        if cur_goal_date:
            try:
                default_date = datetime.fromisoformat(cur_goal_date).date()
            except Exception:
                pass
        g_date = st.date_input("목표 날짜", value=default_date, key=f"goal_date_{name}")

    if st.button("목표 저장", key=f"goal_save_{name}", use_container_width=True):
        res = api_set_goal(name, pin, int(g_amt), g_date.isoformat())
        if res.get("ok"):
            toast("목표 저장 완료!", icon="🎯")
            refresh_account_data(name, pin, force=True)
            st.rerun()
        else:
            st.error(res.get("error", "목표 저장 실패"))

    goal_amount = int(g_amt)
    goal_date = g_date
    current_balance = int(balance)

    bonus = 0
    for s in savings_list:
        if str(s.get("status", "")).lower().strip() != "active":
            continue
        mdt = s.get("maturity_date")
        if not isinstance(mdt, datetime):
            continue
        m_date = mdt.astimezone(KST).date()
        if m_date <= goal_date:
            principal = int(s.get("principal", 0) or 0)
            interest3 = int(s.get("interest", 0) or 0)
            bonus += (principal + interest3)

    expected_amount = current_balance + bonus
    exp_ratio = clamp01((expected_amount / goal_amount) if goal_amount > 0 else 0)

    st.progress(exp_ratio)
    st.write(f"목표일까지 예상 달성률: **{exp_ratio*100:.1f}%**  (예상 {expected_amount} / 목표 {goal_amount})")

    if bonus > 0:
        st.caption(f"※ 목표 날짜({goal_date.isoformat()}) 이전 만기 적금 수령액(원금+이자) +{bonus} 포함")

# =========================
# Sidebar: 계정 만들기/삭제
# =========================
with st.sidebar:
    st.header("➕ 계정 만들기 / 삭제")

    new_name = st.text_input("이름(계정)", key="new_name").strip()
    new_pin = st.text_input("비밀번호(4자리 숫자)", type="password", key="new_pin").strip()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("계정 생성"):
            if not new_name:
                st.error("이름을 입력해 주세요.")
            elif not pin_ok(new_pin):
                st.error("비밀번호는 4자리 숫자여야 해요. (예: 0123)")
            else:
                res = api_create_account(new_name, new_pin)
                if res.get("ok"):
                    toast("계정 생성 완료!")
                    st.session_state.pop("new_name", None)
                    st.session_state.pop("new_pin", None)
                    api_list_accounts_cached.clear()
                    st.rerun()
                else:
                    st.error(res.get("error", "계정 생성 실패"))

    with c2:
        if st.button("삭제"):
            st.session_state.delete_confirm = True

    if st.session_state.delete_confirm:
        st.warning("정말로 삭제하시겠습니까?")
        y, n = st.columns(2)
        with y:
            if st.button("예", key="delete_yes"):
                if not new_name:
                    st.error("삭제할 이름(계정)을 입력해 주세요.")
                elif not pin_ok(new_pin):
                    st.error("비밀번호는 4자리 숫자여야 해요.")
                else:
                    res = api_delete_account(new_name, new_pin)
                    if res.get("ok"):
                        toast("삭제 완료!", icon="🗑️")
                        st.session_state.delete_confirm = False
                        st.session_state.data.pop(new_name, None)
                        api_list_accounts_cached.clear()
                        st.rerun()
                    else:
                        st.error(res.get("error", "삭제 실패"))
        with n:
            if st.button("아니오", key="delete_no"):
                st.session_state.delete_confirm = False
                st.rerun()

# =========================
# Main: 로그인 (이름 저장 체크)
# =========================
st.subheader("🔐 로그인")

qp = st.query_params
saved_name = str(qp.get("saved_name", "") or "")

if not st.session_state.logged_in:
    login_c1, login_c2, login_c3 = st.columns([2, 2, 1])

    with login_c1:
        login_name = st.text_input("이름", value=saved_name, key="login_name_input").strip()
        remember = st.checkbox("이름 저장", value=bool(saved_name), key="remember_name")

    with login_c2:
        login_pin = st.text_input("비밀번호(4자리)", type="password", key="login_pin_input").strip()

    with login_c3:
        login_btn = st.button("로그인", use_container_width=True)

    if login_btn:
        if not login_name:
            st.error("이름을 입력해 주세요.")
        elif not pin_ok(login_pin):
            st.error("비밀번호는 4자리 숫자여야 해요.")
        else:
            if is_admin_login(login_name, login_pin):
                st.session_state.admin_ok = True
                st.session_state.logged_in = True
                st.session_state.login_name = ADMIN_NAME
                st.session_state.login_pin = ADMIN_PIN

                if remember and login_name:
                    st.query_params["saved_name"] = login_name
                else:
                    st.query_params.pop("saved_name", None)

                toast("관리자 모드 ON", icon="🔓")
                st.rerun()
            else:
                doc = fs_auth_student(login_name, login_pin)
                if not doc:
                    st.error("이름 또는 비밀번호가 틀립니다.")
                else:
                    st.session_state.admin_ok = False
                    st.session_state.logged_in = True
                    st.session_state.login_name = login_name
                    st.session_state.login_pin = login_pin

                    if remember and login_name:
                        st.query_params["saved_name"] = login_name
                    else:
                        st.query_params.pop("saved_name", None)

                    toast("로그인 완료!", icon="✅")
                    st.rerun()

else:
    if st.button("로그아웃", key="logout_btn", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.admin_ok = False
        st.session_state.login_name = ""
        st.session_state.login_pin = ""
        st.session_state.tpl_sort_mode = False
        st.session_state.tpl_work_ids = []
        st.session_state.tpl_sort_panel_open = False
        st.rerun()

if not st.session_state.logged_in:
    st.stop()

# =========================
# Templates (공용)
# =========================
tpl_res = api_list_templates_cached()
TEMPLATES = tpl_res.get("templates", []) if tpl_res.get("ok") else []
TEMPLATE_BY_ID = {t["template_id"]: t for t in TEMPLATES}

def template_display_for_trade(t):
    kind_kr = "입금" if t.get("kind") == "deposit" else "출금"
    return f"{t.get('label','')}[{kind_kr} {int(t.get('amount',0) or 0)}]"

# =========================
# ✅ 공용: 템플릿 선택 → 메모/금액 자동 반영 함수
#    (관리자/사용자 동일 로직)
# =========================
def render_template_driven_trade_box(
    prefix: str,
    templates: list[dict],
    template_by_id: dict,
):
    """
    prefix별 session_state를 사용.
    - template_id 선택 시 memo/amount 자동 반영
    - 사용자가 수동으로 수정한 값은 "선택 변경"이 있을 때만 덮어씀
    """
    memo_key = f"{prefix}_memo"
    dep_key = f"{prefix}_dep"
    wd_key = f"{prefix}_wd"
    tpl_key = f"{prefix}_tpl"
    mode_key = f"{prefix}_mode"
    quick_key = f"{prefix}_quick"
    prev_key = f"{prefix}_tpl_prev"

    st.session_state.setdefault(memo_key, "")
    st.session_state.setdefault(dep_key, 0)
    st.session_state.setdefault(wd_key, 0)
    st.session_state.setdefault(tpl_key, "(직접 입력)")
    st.session_state.setdefault(mode_key, "입금(+)")
    st.session_state.setdefault(quick_key, 0)
    st.session_state.setdefault(prev_key, "(직접 입력)")

    tpl_options = ["(직접 입력)"] + [t["template_id"] for t in templates]

    def _tpl_fmt(x):
        if x == "(직접 입력)":
            return "(직접 입력)"
        t = template_by_id.get(x, {})
        return template_display_for_trade(t) if t else str(x)

    sel = st.selectbox("내역 템플릿", tpl_options, key=tpl_key, format_func=_tpl_fmt)

    # ✅ 핵심 수정: 선택이 바뀔 때 자동 반영
    if sel != st.session_state.get(prev_key):
        st.session_state[prev_key] = sel

        if sel != "(직접 입력)":
            tpl = template_by_id.get(sel)
            if tpl:
                st.session_state[memo_key] = str(tpl.get("label", "") or "").strip()

                amt = int(tpl.get("amount", 0) or 0)
                if tpl.get("kind") == "deposit":
                    st.session_state[dep_key] = amt
                    st.session_state[wd_key] = 0
                    st.session_state[mode_key] = "입금(+)"
                else:
                    st.session_state[wd_key] = amt
                    st.session_state[dep_key] = 0
                    st.session_state[mode_key] = "출금(-)"

        # 템플릿을 (직접 입력)로 바꾸면 금액을 자동으로 0으로 만들지는 않음(원하면 수동 수정)

    st.text_input("내역(메모)", key=memo_key)

    QUICK_AMOUNTS = [0, 10, 20, 50, 100, 200, 500, 1000]
    st.radio("적용", ["입금(+)", "출금(-)"], horizontal=True, key=mode_key)

    def _apply_quick():
        amt = int(st.session_state.get(quick_key, 0) or 0)
        if amt == 0:
            return
        if st.session_state[mode_key] == "입금(+)":
            st.session_state[dep_key] = int(st.session_state.get(dep_key, 0) or 0) + amt
            st.session_state[wd_key] = 0
        else:
            st.session_state[wd_key] = int(st.session_state.get(wd_key, 0) or 0) + amt
            st.session_state[dep_key] = 0

    def _fmt_amt(x):
        if x == 0:
            return "0"
        return f"-{x}" if st.session_state[mode_key] == "출금(-)" else f"{x}"

    st.radio(
        "금액 선택",
        QUICK_AMOUNTS,
        horizontal=True,
        key=quick_key,
        format_func=_fmt_amt,
        on_change=_apply_quick
    )

    r1, r2 = st.columns(2)
    with r1:
        st.number_input("입금", min_value=0, step=1, key=dep_key)
    with r2:
        st.number_input("출금", min_value=0, step=1, key=wd_key)

    memo = str(st.session_state.get(memo_key, "") or "").strip()
    dep = int(st.session_state.get(dep_key, 0) or 0)
    wd = int(st.session_state.get(wd_key, 0) or 0)
    return memo, dep, wd

# =========================
# 관리자 화면
# =========================
if st.session_state.admin_ok:
    st.markdown("## 🛡️ 관리자")

    accounts_res = api_list_accounts_cached()
    accounts = accounts_res.get("accounts", []) if accounts_res.get("ok") else []
    if not accounts:
        st.info("활성 계정이 없습니다.")
        st.stop()

    name_search = st.text_input("🔎 계정검색(이름 일부)", key="admin_search").strip()
    filtered = [a for a in accounts if (name_search in a["name"])] if name_search else accounts
    if not filtered:
        st.warning("검색 결과가 없어요.")
        st.stop()

    tab_labels = ["⚙️ 설정", "📒 전체통장"] + [f"👤 {a['name']}" for a in filtered]
    tabs = st.tabs(tab_labels)

    admin_pin = ADMIN_PIN

    # -------------------------
    # ⚙️ 설정 탭
    # -------------------------
    with tabs[0]:
        st.subheader("⚙️ 설정")

        st.markdown("### 🎁 전체 일괄 지급/벌금 (템플릿/빠른 금액)")

        colA, colB = st.columns(2)
        with colA:
            st.markdown("#### ✅ 전체 지급")
            memoA, depA, wdA = render_template_driven_trade_box(
                prefix="admin_bulk_pay",
                templates=TEMPLATES,
                template_by_id=TEMPLATE_BY_ID,
            )

            if st.button("지급 실행", key="bulk_run_setting", use_container_width=True):
                st.session_state.bulk_confirm = True

            if st.session_state.bulk_confirm:
                st.warning("정말로 전체 학생에게 일괄 지급하시겠습니까?")
                y, n = st.columns(2)
                with y:
                    if st.button("예", key="bulk_yes_setting", use_container_width=True):
                        if depA <= 0 or wdA > 0:
                            st.error("지급은 입금(+)만 입력해 주세요.")
                        elif not memoA:
                            st.error("내역(메모)을 입력해 주세요.")
                        else:
                            res = api_admin_bulk_deposit(admin_pin, depA, memoA)
                            if res.get("ok"):
                                toast(f"일괄 지급 완료! ({res.get('count')}명)", icon="🎉")
                                st.session_state.bulk_confirm = False
                                api_list_accounts_cached.clear()
                                st.rerun()
                            else:
                                st.error(res.get("error", "일괄 지급 실패"))
                with n:
                    if st.button("아니오", key="bulk_no_setting", use_container_width=True):
                        st.session_state.bulk_confirm = False
                        st.rerun()

        with colB:
            st.markdown("#### ⚠️ 전체 벌금")
            memoB, depB, wdB = render_template_driven_trade_box(
                prefix="admin_bulk_fine",
                templates=TEMPLATES,
                template_by_id=TEMPLATE_BY_ID,
            )

            if st.button("벌금 실행", key="bulkw_run_setting", use_container_width=True):
                st.session_state.bulk_w_confirm = True

            if st.session_state.bulk_w_confirm:
                st.warning("정말로 전체 학생에게 일괄 벌금을 부과하시겠습니까? (잔액 부족이어도 적용되어 음수 가능)")
                y, n = st.columns(2)
                with y:
                    if st.button("예", key="bulk_w_yes_setting", use_container_width=True):
                        if wdB <= 0 or depB > 0:
                            st.error("벌금은 출금(-)만 입력해 주세요.")
                        elif not memoB:
                            st.error("내역(메모)을 입력해 주세요.")
                        else:
                            res = api_admin_bulk_withdraw(admin_pin, wdB, memoB)
                            if res.get("ok"):
                                toast(f"벌금 완료! (적용 {res.get('count')}명)", icon="⚠️")
                                st.session_state.bulk_w_confirm = False
                                api_list_accounts_cached.clear()
                                st.rerun()
                            else:
                                st.error(res.get("error", "일괄 벌금 실패"))
                with n:
                    if st.button("아니오", key="bulk_w_no_setting", use_container_width=True):
                        st.session_state.bulk_w_confirm = False
                        st.rerun()

        st.divider()

        # 템플릿 추가/수정/삭제 (간단 유지)
        st.markdown("### 🧩 템플릿 추가/수정/삭제")

        KIND_TO_KR = {"deposit": "입금", "withdraw": "출금"}
        KR_TO_KIND = {"입금": "deposit", "출금": "withdraw"}

        templates_now = api_list_templates_cached().get("templates", [])
        mode = st.radio("작업", ["추가", "수정"], horizontal=True, key="tpl_mode_setting2")

        st.session_state.setdefault("tpl_edit_id_setting2", "")
        st.session_state.setdefault("tpl_pick_prev_setting2", None)
        st.session_state.setdefault("tpl_label_setting2", "")
        st.session_state.setdefault("tpl_kind_setting_kr2", "입금")
        st.session_state.setdefault("tpl_amount_setting2", 10)
        st.session_state.setdefault("tpl_order_setting2", 1)

        def tpl_display(t):
            return template_display_for_trade(t)

        def _fill_tpl_form(t):
            st.session_state["tpl_edit_id_setting2"] = t["template_id"]
            st.session_state["tpl_label_setting2"] = t.get("label", "")
            st.session_state["tpl_kind_setting_kr2"] = KIND_TO_KR.get(t.get("kind", "deposit"), "입금")
            st.session_state["tpl_amount_setting2"] = int(t.get("amount", 10) or 10)
            st.session_state["tpl_order_setting2"] = int(t.get("order", 1) or 1)

        if mode == "수정" and templates_now:
            labels = [tpl_display(t) for t in templates_now]
            pick = st.selectbox(
                "수정할 템플릿 선택",
                list(range(len(templates_now))),
                format_func=lambda idx: labels[idx],
                key="tpl_pick_setting2"
            )
            if st.session_state["tpl_pick_prev_setting2"] != pick:
                st.session_state["tpl_pick_prev_setting2"] = pick
                _fill_tpl_form(templates_now[pick])
        elif mode == "추가":
            st.session_state["tpl_edit_id_setting2"] = ""
            st.session_state["tpl_pick_prev_setting2"] = None

        tcol1, tcol2, tcol3 = st.columns([2, 1, 1])
        with tcol1:
            tpl_label = st.text_input("내역 이름", key="tpl_label_setting2").strip()
        with tcol2:
            tpl_kind_kr = st.selectbox("종류", ["입금", "출금"], key="tpl_kind_setting_kr2")
        with tcol3:
            tpl_amount = st.number_input("금액", min_value=1, step=1, key="tpl_amount_setting2")

        tpl_order = st.number_input("순서(order)", min_value=1, step=1, key="tpl_order_setting2")

        if st.button("저장(추가/수정)", key="tpl_save_setting2", use_container_width=True):
            if not tpl_label:
                st.error("내역 이름이 필요합니다.")
            else:
                kind_eng = KR_TO_KIND[tpl_kind_kr]
                tid = st.session_state.get("tpl_edit_id_setting2", "") if mode == "수정" else ""
                res = api_admin_upsert_template(admin_pin, tid, tpl_label, kind_eng, int(tpl_amount), int(tpl_order))
                if res.get("ok"):
                    toast("템플릿 저장 완료!", icon="🧩")
                    api_list_templates_cached.clear()
                    st.rerun()
                else:
                    st.error(res.get("error", "템플릿 저장 실패"))

        st.caption("삭제")
        if templates_now:
            del_labels = [tpl_display(t) for t in templates_now]
            del_pick = st.selectbox(
                "삭제할 템플릿 선택",
                list(range(len(templates_now))),
                format_func=lambda idx: del_labels[idx],
                key="tpl_del_pick_setting2"
            )
            del_id = templates_now[del_pick]["template_id"]
            if st.button("삭제", key="tpl_del_btn_setting2", use_container_width=True):
                st.session_state["tpl_del_confirm_setting2"] = True

            if st.session_state.get("tpl_del_confirm_setting2", False):
                st.warning("정말로 삭제하시겠습니까?")
                y, n = st.columns(2)
                with y:
                    if st.button("예", key="tpl_del_yes_setting2", use_container_width=True):
                        res = api_admin_delete_template(admin_pin, del_id)
                        if res.get("ok"):
                            toast("삭제 완료!", icon="🗑️")
                            st.session_state["tpl_del_confirm_setting2"] = False
                            api_list_templates_cached.clear()
                            st.rerun()
                        else:
                            st.error(res.get("error", "삭제 실패"))
                with n:
                    if st.button("아니오", key="tpl_del_no_setting2", use_container_width=True):
                        st.session_state["tpl_del_confirm_setting2"] = False
                        st.rerun()

        st.divider()
        st.markdown("### 🔧 PIN 재설정")
        target = st.text_input("대상 학생 이름", key="reset_target_setting").strip()
        newp = st.text_input("새 PIN(4자리)", key="reset_pin_setting", type="password").strip()
        if st.button("PIN 변경", key="reset_run_setting", use_container_width=True):
            if not target:
                st.error("대상 이름을 입력해 주세요.")
            elif not pin_ok(newp):
                st.error("새 PIN은 4자리 숫자여야 해요.")
            else:
                res = api_admin_reset_pin(admin_pin, target, newp)
                if res.get("ok"):
                    toast("PIN 변경 완료!", icon="🔧")
                else:
                    st.error(res.get("error", "PIN 변경 실패"))

    # -------------------------
    # 📒 전체통장
    # -------------------------
    with tabs[1]:
        st.subheader("📒 전체통장(사람별 통장 내역)")
        for a in filtered:
            nm, sid = a["name"], a["student_id"]
            sres = api_savings_list_by_student_id(sid)
            savings = sres.get("savings", []) if sres.get("ok") else []
            sv_total = savings_active_total(savings)
            bal_now = int(a.get("balance", 0) or 0)
            asset_total = bal_now + sv_total

            with st.expander(f"👤 {nm}  |  내자산 {asset_total} · 잔액 {bal_now} · 적금 {sv_total}", expanded=False):
                render_asset_summary(bal_now, savings)
                st.markdown("### 📒 통장내역")
                txr = api_get_txs_by_student_id(sid, limit=120)
                if not txr.get("ok"):
                    st.error(txr.get("error", "내역을 불러오지 못했어요."))
                else:
                    df_tx = pd.DataFrame(txr.get("rows", []))
                    if df_tx.empty:
                        st.info("거래 내역이 없어요.")
                    else:
                        df_tx = df_tx.sort_values("created_at_utc", ascending=False)
                        render_tx_table(df_tx)

    # -------------------------
    # 👤 각 사용자별 탭 (개별 관리자 입금/출금 + 되돌리기)
    # -------------------------
    for i, a in enumerate(filtered, start=2):
        with tabs[i]:
            nm, sid = a["name"], a["student_id"]
            st.subheader(f"👤 {nm}")

            txr = api_get_txs_by_student_id(sid, limit=300)
            df_tx = pd.DataFrame(txr.get("rows", [])) if txr.get("ok") else pd.DataFrame()

            sres = api_savings_list_by_student_id(sid)
            savings = sres.get("savings", []) if sres.get("ok") else []
            bal_now = int(a.get("balance", 0) or 0)

            render_asset_summary(bal_now, savings)

            st.markdown("### 🧾 관리자 입금/출금")
            memo, dep, wd = render_template_driven_trade_box(
                prefix=f"admin_ind_{sid}",
                templates=TEMPLATES,
                template_by_id=TEMPLATE_BY_ID,
            )
            st.caption("※ 관리자 출금(벌금)은 잔액 부족이어도 적용되어 통장 잔액이 음수가 될 수 있어요.")

            if st.button("저장(관리자)", key=f"admin_ind_save_{sid}", use_container_width=True):
                if not memo:
                    st.error("내역(메모)을 입력해 주세요.")
                elif (dep > 0 and wd > 0) or (dep == 0 and wd == 0):
                    st.error("입금/출금은 둘 중 하나만 입력해 주세요.")
                else:
                    res = api_admin_add_tx_by_student_id(ADMIN_PIN, sid, memo, dep, wd)
                    if res.get("ok"):
                        toast("저장 완료!", icon="✅")
                        api_list_accounts_cached.clear()
                        st.rerun()
                    else:
                        st.error(res.get("error", "저장 실패"))

            st.divider()
            st.markdown("### 📒 통장내역")
            if not df_tx.empty:
                df_tx = df_tx.sort_values("created_at_utc", ascending=False)
                render_tx_table(df_tx)

            st.divider()
            st.markdown("### ↩️ 되돌리기(적금 내역 제외)")
            if df_tx is None or df_tx.empty:
                st.caption("거래 내역이 없어요.")
            else:
                show_df = df_tx.copy()
                show_df["선택"] = False
                view = show_df[["tx_id", "memo", "deposit", "withdraw", "balance_after", "created_at_kr"]].rename(columns={
                    "memo": "내역",
                    "deposit": "입금",
                    "withdraw": "출금",
                    "balance_after": "총액",
                    "created_at_kr": "날짜-시간"
                })
                edited = st.data_editor(
                    view,
                    use_container_width=True,
                    hide_index=True,
                    disabled=["tx_id", "내역", "입금", "출금", "총액", "날짜-시간"],
                    key=f"rb_editor_{sid}",
                    column_config={"tx_id": None},
                )
                # data_editor는 체크 컬럼이 없어서, 간단하게 multiselect로 제공
                options = [
                    (row["tx_id"], f"{row['내역']} | {row['날짜-시간']}")
                    for _, row in view.iterrows()
                ]
                pick = st.multiselect(
                    "되돌릴 거래 선택",
                    options=options,
                    format_func=lambda x: x[1],
                    key=f"rb_pick_{sid}"
                )
                tx_ids = [x[0] for x in pick]

                admin_pin_in = st.text_input("관리자 PIN", type="password", key=f"rb_pin_{sid}")
                if st.button("선택 내역 되돌리기", key=f"rb_run_{sid}", use_container_width=True):
                    res = api_admin_rollback_selected(admin_pin_in, sid, tx_ids)
                    if res.get("ok"):
                        toast(f"되돌리기 완료! ({res.get('undone', 0)}건)", icon="↩️")
                        if res.get("message"):
                            st.info(res.get("message"))
                        api_list_accounts_cached.clear()
                        st.rerun()
                    else:
                        st.error(res.get("error", "되돌리기 실패"))

            st.divider()
            render_active_savings_list(savings, name=f"admin_view_{nm}", pin="0000")

    st.stop()

# =========================
# 사용자 화면
# =========================
name = st.session_state.login_name
pin = st.session_state.login_pin

mat = maybe_check_maturities(name, pin)
if mat and mat.get("ok") and mat.get("matured_count", 0) > 0:
    st.success(f"🎉 만기 도착! 적금 {mat['matured_count']}건 자동 반환 (+{mat['paid_total']} 포인트)")

refresh_account_data(name, pin, force=True)
slot = st.session_state.data.get(name, {})
if slot.get("error"):
    st.error(slot["error"])
    st.stop()

df_tx = slot.get("df_tx", pd.DataFrame())
balance = int(slot.get("balance", 0))
savings = slot.get("savings", [])
student_id = slot.get("student_id", "")

render_asset_summary(balance, savings)

t1, t2, t3 = st.tabs(["🧾 입금/출금", "💰 적금", "🎯 목표"])

# -------------------------
# 🧾 입금/출금
# -------------------------
with t1:
    st.subheader("🧾 입금/출금")

    # ✅ 여기(사용자)도 템플릿 선택 시 자동 반영되도록 동일 함수 사용 (이번 수정 핵심)
    memo, dep, wd = render_template_driven_trade_box(
        prefix=f"user_trade_{student_id}",
        templates=TEMPLATES,
        template_by_id=TEMPLATE_BY_ID,
    )

    # 사용자 규칙 안내
    if balance < 0:
        st.warning("현재 통장 잔액이 음수입니다. (출금/적금 가입 불가)")

    if st.button("저장", key=f"user_trade_save_{student_id}", use_container_width=True):
        if not memo:
            st.error("내역(메모)을 입력해 주세요.")
        elif (dep > 0 and wd > 0) or (dep == 0 and wd == 0):
            st.error("입금/출금은 둘 중 하나만 입력해 주세요.")
        else:
            # ✅ 음수 잔액이면 출금/적금 불가 (입금은 가능)
            if balance < 0 and wd > 0:
                st.error("잔액이 음수인 경우 출금은 불가합니다. 먼저 입금으로 잔액을 0 이상으로 만들어 주세요.")
            else:
                res = api_add_tx(name, pin, memo, dep, wd)
                if res.get("ok"):
                    toast("저장 완료!", icon="✅")
                    refresh_account_data(name, pin, force=True)
                    st.rerun()
                else:
                    st.error(res.get("error", "저장 실패"))

    st.divider()
    st.markdown("### 📒 통장내역")
    render_tx_table(df_tx)

# -------------------------
# 💰 적금
# -------------------------
with t2:
    st.subheader("💰 적금")

    # ✅ 음수 잔액이면 적금 불가
    if balance < 0:
        st.warning("현재 통장 잔액이 음수라서 적금 가입은 불가합니다. 먼저 입금해 주세요.")

    c1, c2 = st.columns(2)
    with c1:
        principal = st.number_input("원금(10단위)", min_value=0, step=10, value=0, key=f"sv_pr_{student_id}")
    with c2:
        weeks = st.selectbox("기간(주)", [1,2,3,4,5,6,7,8,9,10], index=1, key=f"sv_wk_{student_id}")

    r = rate_by_weeks(int(weeks))
    interest = round(int(principal) * r) if principal else 0
    st.caption(f"이자율: {r*100:.0f}%  |  만기 이자(예상): {interest}")

    if st.button("적금 가입", key=f"sv_join_{student_id}", use_container_width=True, disabled=(balance < 0)):
        res = api_savings_create(name, pin, principal, weeks)
        if res.get("ok"):
            toast("적금 가입 완료!", icon="💰")
            refresh_account_data(name, pin, force=True)
            st.rerun()
        else:
            st.error(res.get("error", "적금 가입 실패"))

    st.divider()
    render_active_savings_list(savings, name=name, pin=pin)

# -------------------------
# 🎯 목표
# -------------------------
with t3:
    st.subheader("🎯 목표")
    render_goal_section(name, pin, balance, savings)
