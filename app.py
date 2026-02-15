import streamlit as st
import pandas as pd

# ✅ Altair(차트) - 없어도 앱이 죽지 않게 안전 import
try:
    import altair as alt
except Exception:
    alt = None

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
    @media (max-width: 768px) {
        .block-container { padding-bottom: 6.0rem; }
    }

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
    .tpl-head { font-weight: 800; padding: 6px 6px; border-bottom: 2px solid #ddd; margin-bottom: 4px; }
    .tpl-cell { padding: 4px 6px; border-bottom: 1px solid #eee; line-height: 1.15; font-size: 0.95rem; }
    .tpl-label { font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    @media (max-width: 768px){
        .tpl-cell { padding: 6px 6px; font-size: 1.02rem; line-height: 1.18; }
        .tpl-label{
            white-space: normal;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow:hidden;
        }
        .tpl-sub { font-size: 0.92rem; line-height: 1.12; }
    }
    .tpl-sub { color:#666; font-size: 0.85rem; margin-top: 2px; line-height: 1.05; }

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
    .tpl-simple .item { padding: 8px 0; border-bottom: 1px dashed #e6e6e6; }
    .tpl-simple .item:last-child { border-bottom: none; }
    .tpl-simple .idx { font-weight: 900; margin-right: 8px; }
    .tpl-simple .lab { font-weight: 800; }
    .tpl-simple .meta { color:#666; font-size: 0.92rem; margin-top: 2px; }

/* ✅ 빠른 금액: radiogroup 라벨을 "원형 버튼"처럼 */
.round-btns div[role="radiogroup"]{
    gap: 0.35rem !important;
}

.round-btns div[role="radiogroup"] > label{
    border-radius: 9999px !important;
    padding: 0 !important;
    width: 2.6rem !important;
    height: 2.6rem !important;
    min-width: 2.6rem !important;
    min-height: 2.6rem !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    font-size: 0.95rem !important;
    line-height: 1 !important;
}

@media (max-width: 768px){
    .round-btns div[role="radiogroup"] > label{
        width: 3.1rem !important;
        height: 3.1rem !important;
        min-width: 3.1rem !important;
        min-height: 3.1rem !important;
        font-size: 1.05rem !important;
    }
}

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
# (PATCH) 국고(세입/세출) 기록: 직업/월급 공제에서 사용
# - 기존 house 앱에 국고 API가 없어서 NameError가 나던 부분을 안전 처리
# - admin_pin 검증을 따로 하지 않는 구조면, ADMIN_PIN으로만 호출되도록 제한
# =========================
def api_add_treasury_tx(admin_pin: str, memo: str, income: int = 0, expense: int = 0, actor: str = "salary_auto"):
    try:
        if str(admin_pin) != str(ADMIN_PIN):
            return {"ok": False, "error": "관리자 PIN이 틀립니다."}
        memo = (memo or "").strip()
        income = int(income or 0)
        expense = int(expense or 0)
        if not memo:
            return {"ok": False, "error": "내역이 필요합니다."}
        if (income > 0 and expense > 0) or (income == 0 and expense == 0):
            return {"ok": False, "error": "세입/세출 중 하나만 입력하세요."}

        db.collection("treasury").add(
            {
                "memo": memo,
                "income": int(income),
                "expense": int(expense),
                "actor": actor,
                "created_at": datetime.now(KST).isoformat(),
            }
        )
        return {"ok": True}
    except Exception as e:
        # 국고 컬렉션이 아직 없어도 앱이 죽지 않게
        return {"ok": False, "error": str(e)}


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


def compute_preview(principal: int, weeks: int):
    r = rate_by_weeks(weeks)
    interest = round(principal * r)
    maturity = principal + interest
    maturity_date = (datetime.now(KST) + timedelta(days=weeks * 7)).date()
    return r, interest, maturity, maturity_date


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
        st.metric("총 자산", f"{asset_total}")
    with c2:
        st.metric("통장 잔액", f"{int(balance_now)}")
    with c3:
        st.metric("적금 총액", f"{int(sv_total)}")


def savings_active_total(savings_list: list[dict]) -> int:
    return sum(
        int(s.get("principal", 0) or 0)
        for s in savings_list
        if str(s.get("status", "")).lower() == "active"
    )


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
            items.append({"student_id": d.id, "name": nm, "balance": int(s.get("balance", 0) or 0)})
    items.sort(key=lambda x: x["name"])
    return {"ok": True, "accounts": items}


@st.cache_data(ttl=300, show_spinner=False)
def api_list_templates_cached():
    docs = db.collection("templates").stream()
    templates = []
    for d in docs:
        t = d.to_dict() or {}
        if t.get("label"):
            templates.append(
                {
                    "template_id": d.id,
                    "label": t.get("label"),
                    "kind": t.get("kind"),
                    "amount": int(t.get("amount", 0) or 0),
                    "order": int(t.get("order", 999999) or 999999),
                }
            )
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
    db.collection("students").document().set(
        {"name": name, "pin": pin, "balance": 0, "is_active": True, "created_at": firestore.SERVER_TIMESTAMP}
    )
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

        # 일반 출금은 잔액 부족이면 불가
        if tx_type == "withdraw" and bal < withdraw:
            raise ValueError("잔액보다 큰 출금은 불가합니다.")

        new_bal = bal + amount
        transaction.update(student_ref, {"balance": new_bal})
        transaction.set(
            tx_ref,
            {
                "student_id": student_doc.id,
                "type": tx_type,
                "amount": amount,
                "balance_after": new_bal,
                "memo": memo,
                "created_at": firestore.SERVER_TIMESTAMP,
            },
        )
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
        transaction.set(
            tx_ref,
            {
                "student_id": student_id,
                "type": tx_type,
                "amount": amount,
                "balance_after": new_bal,
                "memo": memo,
                "created_at": firestore.SERVER_TIMESTAMP,
            },
        )
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
        rows.append(
            {
                "tx_id": d.id,
                "created_at_utc": created_dt_utc,
                "created_at_kr": format_kr_datetime(created_dt_utc.astimezone(KST)) if created_dt_utc else "",
                "memo": tx.get("memo", ""),
                "type": tx.get("type", ""),
                "amount": amt,
                "deposit": amt if amt > 0 else 0,
                "withdraw": -amt if amt < 0 else 0,
                "balance_after": int(tx.get("balance_after", 0) or 0),
            }
        )
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
        msg = "선택한 항목이 모두 되돌리기 불가합니다."
        if blocked:
            msg += " (예: 적금/이미 되돌림)"
        return {"ok": False, "error": msg}

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
            transaction.set(
                rollback_ref,
                {
                    "student_id": student_id,
                    "type": "rollback",
                    "amount": rollback_amount,
                    "balance_after": new_bal,
                    "memo": f"{tid} 되돌리기",
                    "related_tx": tid,
                    "created_at": firestore.SERVER_TIMESTAMP,
                },
            )
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
        out.append(
            {
                "savings_id": d.id,
                "principal": int(s.get("principal", 0) or 0),
                "weeks": int(s.get("weeks", 0) or 0),
                "interest": int(s.get("interest", 0) or 0),
                "maturity_date": _to_utc_datetime(s.get("maturity_date")),
                "status": s.get("status", "active"),
            }
        )
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
        transaction.set(
            tx_ref,
            {
                "student_id": student_doc.id,
                "type": "withdraw",
                "amount": -principal,
                "balance_after": new_bal,
                "memo": f"적금 가입({weeks}주)",
                "created_at": firestore.SERVER_TIMESTAMP,
            },
        )
        transaction.set(
            savings_ref,
            {
                "student_id": student_doc.id,
                "principal": principal,
                "weeks": weeks,
                "interest": interest,
                "start_date": firestore.SERVER_TIMESTAMP,
                "maturity_date": maturity_date,
                "status": "active",
            },
        )
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
        transaction.set(
            tx_ref,
            {
                "student_id": student_doc.id,
                "type": "deposit",
                "amount": principal,
                "balance_after": new_bal,
                "memo": f"적금 해지({weeks}주)",
                "created_at": firestore.SERVER_TIMESTAMP,
            },
        )
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
            transaction.set(
                tx_ref,
                {
                    "student_id": student_doc.id,
                    "type": "maturity",
                    "amount": amount,
                    "balance_after": new_bal,
                    "memo": f"적금 만기({weeks}주)",
                    "created_at": firestore.SERVER_TIMESTAMP,
                },
            )
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
    """ ✅ 관리자/사용자 공용 조회: student_id 기준 목표 조회 """
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
        "goal_date": str(g.get("goal_date", "") or ""),
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
        db.collection("goals").document(docs[0].id).update({"target_amount": goal_amount, "goal_date": goal_date_str})
    else:
        db.collection("goals").document().set(
            {
                "student_id": student_doc.id,
                "title": "목표",
                "target_amount": goal_amount,
                "goal_date": goal_date_str,
                "created_at": firestore.SERVER_TIMESTAMP,
            }
        )
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
            transaction.set(
                tx_ref,
                {
                    "student_id": student_id,
                    "type": "deposit",
                    "amount": amount,
                    "balance_after": new_bal,
                    "memo": memo,
                    "created_at": firestore.SERVER_TIMESTAMP,
                },
            )

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
            transaction.set(
                tx_ref,
                {
                    "student_id": student_id,
                    "type": "withdraw",
                    "amount": -amount,
                    "balance_after": new_bal,
                    "memo": memo,
                    "created_at": firestore.SERVER_TIMESTAMP,
                },
            )

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
            str((x[1] or {}).get("label", "")),
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
# (class앱 이식) 직업/투자 요약 helpers + 투자/직업 탭 렌더
# =========================
INV_PROD_COL = "invest_products"
INV_LEDGER_COL = "invest_ledger"

@st.cache_data(ttl=60, show_spinner=False)
def _get_role_name_by_student_id(student_id: str) -> str:
    try:
        sid = str(student_id or "").strip()
        if not sid:
            return "없음"

        # (1) students 문서에서 먼저 찾기 (job_name/job/role_id/job_role_id/job_id 등)
        snap = db.collection("students").document(sid).get()
        if snap.exists:
            sdata = snap.to_dict() or {}

            rid = str(
                sdata.get("role_id")
                or sdata.get("job_role_id")
                or sdata.get("job_id")
                or ""
            ).strip()

            # ✅ 학생 문서에 job_name/job이 직접 들어있는 경우
            job_direct = str(sdata.get("job_name") or sdata.get("job") or "").strip()
            if job_direct:
                return job_direct

            # ✅ role_id가 있으면 roles 컬렉션에서 이름 조회
            if rid:
                rdoc = db.collection("roles").document(rid).get()
                if rdoc.exists:
                    r = rdoc.to_dict() or {}
                    nm = str(r.get("role_name") or r.get("name") or rid).strip()
                    return nm if nm else rid

                # roles 문서가 없으면 role_id 자체를 직업명으로 보여주기
                return rid

        # (2) students에 없으면 job_salary에서 assigned_ids로 찾기 (직업/월급 탭 방식)
        jobs = []
        for jdoc in db.collection("job_salary").stream():
            jd = jdoc.to_dict() or {}
            assigned = [str(x) for x in (jd.get("assigned_ids", []) or [])]
            if sid in assigned:
                jname = str(jd.get("job") or jd.get("role_name") or "").strip()
                if jname:
                    jobs.append(jname)

        if jobs:
            # 중복 제거(순서 유지)
            uniq = []
            for j in jobs:
                if j not in uniq:
                    uniq.append(j)
            return ", ".join(uniq)

        return "없음"

    except Exception:
        return "없음"

@st.cache_data(ttl=30, show_spinner=False)
def _get_invest_summary_by_student_id(student_id: str) -> tuple[str, int]:
    """
    ✅ return (표시문구, 투자총액_현재가치추정)
    - 표시문구 예: "국어 100드림" / 여러개면 "국어 100드림, 수학 50드림"
    - invest_ledger: redeemed=False 항목을 보유로 간주
    - invest_products: current_price 사용 + 종목명(name/label/title/subject) 대응
    """
    try:
        sid = str(student_id)

        # 1) 종목 정보 맵 (id -> (name, current_price))
        prod_map = {}
        for d in db.collection(INV_PROD_COL).stream():
            x = d.to_dict() or {}
            pid = str(x.get("product_id", d.id) or d.id)

            pname = (
                str(x.get("name", "") or "").strip()
                or str(x.get("label", "") or "").strip()
                or str(x.get("title", "") or "").strip()
                or str(x.get("subject", "") or "").strip()
                or pid
            )
            cur_price = float(x.get("current_price", 0.0) or 0.0)
            prod_map[pid] = (pname, cur_price)

        # 2) 보유 장부(미환매) → 종목별 현재가치 합산
        q = db.collection(INV_LEDGER_COL).where(filter=FieldFilter("student_id", "==", sid)).stream()
        per_prod_val = {}  # pid -> value

        for d in q:
            x = d.to_dict() or {}
            if bool(x.get("redeemed", False)):
                continue

            pid = str(x.get("product_id", "") or "")
            if not pid:
                continue

            buy_price = float(x.get("buy_price", 0.0) or 0.0)
            invest_amount = int(x.get("invest_amount", 0) or 0)

            pname, cur_price = prod_map.get(pid, (pid, 0.0))

            # 현재가치(대략): 투자금 * (현재가/매수가)
            if buy_price > 0 and cur_price > 0:
                cur_val = invest_amount * (cur_price / buy_price)
            else:
                cur_val = invest_amount

            per_prod_val[pid] = per_prod_val.get(pid, 0) + cur_val

        if not per_prod_val:
            return ("없음", 0)

        # 총합
        total_val = int(round(sum(v for v in per_prod_val.values())))

        # 표시: 종목별(내림차순) 상위 3개만
        items = sorted(per_prod_val.items(), key=lambda kv: kv[1], reverse=True)
        shown = []
        for pid, v in items[:3]:
            pname = prod_map.get(pid, (pid, 0.0))[0]
            shown.append(f"{pname} {int(round(v))}드림")
        text = ", ".join(shown)
        if len(items) > 3:
            text += f" 외 {len(items)-3}개"

        return (text, total_val)
    except Exception:
        return ("없음", 0)


@st.cache_data(ttl=30, show_spinner=False)
def _get_invest_principal_by_student_id(student_id: str) -> tuple[str, int]:
    """
    ✅ return (표시문구, 투자원금합계)
    - 표시문구 예: "국어 100드림, 수학 50드림"
    - invest_ledger: redeemed=False 항목의 invest_amount를 '원금'으로 간주해 종목별 합산
    """
    try:
        sid = str(student_id)

        # 1) 종목 정보 맵 (id -> name)
        prod_name = {}
        for d in db.collection(INV_PROD_COL).stream():
            x = d.to_dict() or {}
            pid = str(x.get("product_id", d.id) or d.id)
            pname = (
                str(x.get("name", "") or "").strip()
                or str(x.get("label", "") or "").strip()
                or str(x.get("title", "") or "").strip()
                or str(x.get("subject", "") or "").strip()
                or pid
            )
            prod_name[pid] = pname

        # 2) 보유 장부(미환매) → 종목별 원금 합산
        q = db.collection(INV_LEDGER_COL).where(filter=FieldFilter("student_id", "==", sid)).stream()
        per_prod_amt = {}  # pid -> principal(sum invest_amount)

        for d in q:
            x = d.to_dict() or {}
            if bool(x.get("redeemed", False)):
                continue

            pid = str(x.get("product_id", "") or "")
            if not pid:
                continue

            invest_amount = int(x.get("invest_amount", 0) or 0)
            if invest_amount <= 0:
                continue

            per_prod_amt[pid] = per_prod_amt.get(pid, 0) + invest_amount

        if not per_prod_amt:
            return ("없음", 0)

        total_principal = int(sum(int(v) for v in per_prod_amt.values()))

        # 표시: 종목별(내림차순) 최대 6개, 그 이상이면 상위 3개 + 외 n개
        items = sorted(per_prod_amt.items(), key=lambda kv: kv[1], reverse=True)

        shown = []
        if len(items) <= 6:
            for pid, v in items:
                shown.append(f"{prod_name.get(pid, pid)} {int(v)}드림")
        else:
            for pid, v in items[:3]:
                shown.append(f"{prod_name.get(pid, pid)} {int(v)}드림")
            shown.append(f"외 {len(items)-3}개")

        return (", ".join(shown), total_principal)

    except Exception:
        return ("없음", 0)


def _render_invest_admin_like(*, inv_admin_ok_flag: bool, force_is_admin: bool, my_student_id, login_name, login_pin):
    """관리자 투자 화면을 동일하게 렌더링(권한 학생의 투자(관리자) 탭에서도 동일 UI/기능)."""
    # ✅ 이 함수 내부에서는 is_admin 값을 force_is_admin으로 "가상" 설정해서
    #    관리자 화면 분기(학생용 UI 숨김 등)가 관리자와 동일하게 동작하게 한다.
    is_admin = bool(force_is_admin)
    inv_admin_ok = bool(inv_admin_ok_flag)  # ✅ 관리자 기능 실행 허용 여부(권한)
    
    INV_PROD_COL = "invest_products"
    INV_HIST_COL = "invest_price_history"
    INV_LEDGER_COL = "invest_ledger"
    
    
    # ✅ (PATCH) 투자 탭 - 종목별 '주가 변동 내역' 표 글자/패딩 축소 전용 CSS
    st.markdown(
        """
        <style>
        table.inv_hist_table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
            line-height: 1.15;
        }
        table.inv_hist_table th, table.inv_hist_table td {
            padding: 6px 8px;
            border: 1px solid rgba(0,0,0,0.08);
            vertical-align: middle;
        }
        table.inv_hist_table th {
            font-weight: 700;
            background: rgba(0,0,0,0.03);
            text-align: center;  /* ✅ 제목셀만 중앙정렬 */
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# -------------------------
    # 유틸(함수 대신 안전하게 inline)
    # -------------------------
    days_ko = ["월", "화", "수", "목", "금", "토", "일"]
    
    def _as_price1(v):
        try:
            return float(f"{float(v):.1f}")
        except Exception:
            return 0.0
    
    def _ts_to_dt(v):
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        try:
            if hasattr(v, "to_datetime"):
                out = v.to_datetime()
                if isinstance(out, datetime):
                    return out
        except Exception:
            pass
        return None
    
    def _fmt_kor_date_md(dt_obj):
        if not dt_obj:
            return "-"
        try:
            dt_kst = dt_obj.astimezone(KST)
        except Exception:
            dt_kst = dt_obj
        try:
            wd = days_ko[int(dt_kst.weekday())]
        except Exception:
            wd = ""
        return f"{dt_kst.month}월 {dt_kst.day}일({wd})"
    
    # -------------------------
    # 권한: 지급(회수) 가능?
    # - 관리자 or 직업 '투자증권'
    # -------------------------
    def _can_redeem(actor_student_id: str) -> bool:
        if inv_admin_ok:
            return True
        try:
            if not actor_student_id:
                return False
            snap = db.collection("students").document(str(actor_student_id)).get()
            if not snap.exists:
                return False
            rid = str((snap.to_dict() or {}).get("role_id", "") or "")
            if not rid:
                return False
            roles = api_list_roles_cached()
            for r in roles:
                if str(r.get("role_id")) == rid:
                    return str(r.get("role_name", "") or "") == "투자증권"
            return False
        except Exception:
            return False
    
    # -------------------------
    # 장부 로드
    # -------------------------
    def _load_ledger(for_student_id: str | None):
        try:
            q = (
                db.collection(INV_LEDGER_COL)
                .order_by("buy_at", direction=firestore.Query.DESCENDING)
                .limit(400)
                .stream()
            )
            rows = []
            for d in q:
                x = d.to_dict() or {}
                if for_student_id and str(x.get("student_id")) != str(for_student_id):
                    continue
                rows.append({**x, "_doc_id": d.id})
            return rows
        except Exception:
            # fallback(인덱스 등)
            try:
                q = db.collection(INV_LEDGER_COL).limit(400).stream()
                rows = []
                for d in q:
                    x = d.to_dict() or {}
                    if for_student_id and str(x.get("student_id")) != str(for_student_id):
                        continue
                    rows.append({**x, "_doc_id": d.id})
                return rows
            except Exception:
                return []
    
    # -------------------------
    # 주가 변동 내역 로드 (표용)
    # -------------------------
    def _get_history(product_id: str, limit=120):
        pid = str(product_id)
        out = []
        # 1) 인덱스 OK일 때
        try:
            q = (
                db.collection(INV_HIST_COL)
                .where(filter=FieldFilter("product_id", "==", pid))
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(int(limit))
                .stream()
            )
            for d in q:
                x = d.to_dict() or {}
                out.append(
                    {
                        "created_at": x.get("created_at"),
                        "reason": str(x.get("reason", "") or "").strip(),
                        "price_before": _as_price1(x.get("price_before", x.get("price", 0.0))),
                        "price_after": _as_price1(x.get("price_after", x.get("price", 0.0))),
                    }
                )
            return out
        except Exception:
            pass
    
        # 2) fallback
        try:
            q = (
                db.collection(INV_HIST_COL)
                .where(filter=FieldFilter("product_id", "==", pid))
                .limit(int(limit))
                .stream()
            )
            for d in q:
                x = d.to_dict() or {}
                out.append(
                    {
                        "created_at": x.get("created_at"),
                        "reason": str(x.get("reason", "") or "").strip(),
                        "price_before": _as_price1(x.get("price_before", x.get("price", 0.0))),
                        "price_after": _as_price1(x.get("price_after", x.get("price", 0.0))),
                    }
                )
            out.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
            return out
        except Exception:
            return []
    
    # -------------------------
    # 종목 로드
    # -------------------------
    def _get_products(active_only=True):
        try:
            q = db.collection(INV_PROD_COL)
            if active_only:
                q = q.where(filter=FieldFilter("is_active", "==", True))
            docs = q.stream()
            out = []
            for d in docs:
                x = d.to_dict() or {}
                nm = str(x.get("name", "") or "").strip()
                if not nm:
                    continue
                out.append(
                    {
                        "product_id": d.id,
                        "name": nm,
                        "current_price": _as_price1(x.get("current_price", 0.0)),
                        "is_active": bool(x.get("is_active", True)),
                    }
                )
            out.sort(key=lambda r: r["name"])
            return out
        except Exception:
            return []
    
    # -------------------------
    # 회수 계산(÷10)
    # -------------------------
    def _calc_redeem_amount(invest_amount: int, buy_price: float, sell_price: float):
        invest_amount = int(invest_amount or 0)
        buy_price = _as_price1(buy_price)
        sell_price = _as_price1(sell_price)
        diff = _as_price1(sell_price - buy_price)
    
        # diff <= -100 : 전액 손실
        if diff <= -100:
            profit = -invest_amount
            redeem_amt = 0
        else:
            profit = invest_amount * float(diff) / 10.0  # ✅ 나누기 10
            redeem_amt = invest_amount + profit
            if redeem_amt < 0:
                redeem_amt = 0
    
        return diff, profit, int(round(redeem_amt))
    
    # -------------------------------------------------
    # 1) (상단) 종목 및 주가 변동
    # -------------------------------------------------
    st.markdown("### 📈 종목 및 주가 변동")
    
    # (사용자) 상단 요약: 통장 잔액 / 투자 원금 / 현재 평가
    if not is_admin:
        # 1) 통장 잔액
        cur_bal = 0
        try:
            if my_student_id:
                s = db.collection("students").document(str(my_student_id)).get()
                if s.exists:
                    cur_bal = int((s.to_dict() or {}).get("balance", 0) or 0)
        except Exception:
            cur_bal = 0

        # 2) 투자 원금 / 현재 평가
        principal_total = 0
        eval_total = 0
        principal_by_name = {}
        eval_by_name = {}

        def _add_sum(d, k, v):
            d[k] = int(d.get(k, 0) or 0) + int(v or 0)

        def _fmt_breakdown(d):
            items = []
            for k in sorted(d.keys()):
                v = int(d.get(k, 0) or 0)
                if v > 0:
                    items.append(f"{k} {v}드림")
            return ", ".join(items) if items else "없음"

        try:
            prods_now = _get_products(active_only=True)
            price_by_id = {str(p["product_id"]): float(p.get("current_price", 0.0) or 0.0) for p in prods_now}
            name_by_id = {str(p["product_id"]): str(p.get("name", "") or "") for p in prods_now}

            my_rows = _load_ledger(my_student_id)

            for r in my_rows:
                if bool(r.get("redeemed", False)):
                    continue

                amt = int(r.get("invest_amount", 0) or 0)
                if amt <= 0:
                    continue

                pid = str(r.get("product_id", "") or "")
                nm = str(r.get("product_name", "") or "").strip()
                if not nm:
                    nm = str(name_by_id.get(pid, "") or "").strip()
                if not nm:
                    nm = "미지정"

                buy_price = float(r.get("buy_price", 0.0) or 0.0)
                cur_price = float(price_by_id.get(pid, 0.0) or 0.0)

                # ✅ 현재 평가(거래 탭 기준): 투자금 * (현재가/매입가)
                if buy_price > 0 and cur_price > 0:
                    cur_val = amt * (cur_price / buy_price)
                else:
                    cur_val = amt

                _add_sum(principal_by_name, nm, amt)
                _add_sum(eval_by_name, nm, int(round(cur_val)))

            principal_total = sum(principal_by_name.values())
            eval_total = sum(eval_by_name.values())

        except Exception:
            principal_total = 0
            eval_total = 0
            principal_by_name = {}
            eval_by_name = {}

        st.markdown(f"**💰 통장 잔액:** {cur_bal}드림")
        st.markdown(f"**🪙 투자 원금:** 총 {principal_total}드림({_fmt_breakdown(principal_by_name)})")
        st.markdown(f"**📈 현재 평가:** 총 {eval_total}드림({_fmt_breakdown(eval_by_name)})")
        st.divider()

    
    products = _get_products(active_only=True)
    if not products:
        st.info("등록된 투자 종목이 없습니다. (관리자) 아래에서 종목을 먼저 추가해 주세요.")
    else:
        for p in products:
            nm = p["name"]
            cur = p["current_price"]
            st.markdown(f"- **{nm}** (현재주가 **{cur:.1f}**)")
    
            if inv_admin_ok:
                with st.expander(f"{nm} 주가 변동 반영", expanded=False):
                    c1, c2, c3 = st.columns([3.2, 2.2, 1.2], gap="small")
                    with c1:
                        reason = st.text_input("변동 사유", key=f"inv_reason_{p['product_id']}")
                    with c2:
                        new_price = st.number_input(
                            "주가",
                            min_value=0.0,
                            max_value=999.9,
                            step=0.1,
                            format="%.1f",
                            value=float(cur),
                            key=f"inv_price_{p['product_id']}",
                        )
                    with c3:
                        save_btn = st.button("저장", use_container_width=True, key=f"inv_save_{p['product_id']}")
    
                    if save_btn:
                        reason2 = str(reason or "").strip()
                        if not reason2:
                            st.warning("변동 사유를 입력해 주세요.")
                        else:
                            try:
                                payload = {
                                    "product_id": p["product_id"],
                                    "reason": reason2,
                                    "price_before": _as_price1(cur),
                                    "price_after": _as_price1(new_price),
                                    "created_at": firestore.SERVER_TIMESTAMP,
                                }
                                db.collection(INV_HIST_COL).document().set(payload)
                                db.collection(INV_PROD_COL).document(p["product_id"]).set(
                                    {"current_price": _as_price1(new_price), "updated_at": firestore.SERVER_TIMESTAMP},
                                    merge=True,
                                )
                                toast("주가가 반영되었습니다.", icon="✅")
                                st.rerun()
                            except Exception as e:
                                st.error(f"저장 실패: {e}")
    
                    # 변동 내역(표)
                    hist = _get_history(p["product_id"], limit=120)
                    if hist:
                        rows = []
                        for h in hist:
                            dt = _ts_to_dt(h.get("created_at"))
                            pb = float(h.get("price_before", 0.0) or 0.0)
                            pa = float(h.get("price_after", 0.0) or 0.0)
                            diff = round(pa - pb, 1)
    
                            # 변동일시: 0월 0일(요일) 오전/오후 00시 00분
                            def _fmt_kor_datetime(dt_obj):
                                if not dt_obj:
                                    return "-"
                                try:
                                    dt_kst = dt_obj.astimezone(KST)
                                except Exception:
                                    dt_kst = dt_obj
    
                                hour = dt_kst.hour
                                ampm = "오전" if hour < 12 else "오후"
                                hh = hour if 1 <= hour <= 12 else (hour - 12 if hour > 12 else 12)
                                return f"{dt_kst.month}월 {dt_kst.day}일({days_ko[dt_kst.weekday()]}) {ampm} {hh:02d}시 {dt_kst.minute:02d}분"
    
                            # 주가 등락 표시 (요청: 하락은 파란 아이콘+파란 글씨)
                            if diff > 0:
                                diff_view = f"<span style='color:red'>▲ +{diff:.1f}</span>"
                            elif diff < 0:
                                diff_view = f"<span style='color:blue'>▼ {diff:.1f}</span>"
                            else:
                                diff_view = "-"
    
                            rows.append(
                                {
                                    "변동일시": _fmt_kor_datetime(dt),
                                    "변동사유": h.get("reason", "") or "",
                                    "주가": f"{pa:.1f}",          # ✅ '변동 후' → '주가'
                                    "주가 등락": diff_view,
                                }
                            )
    
                        df = pd.DataFrame(rows)
    
                        # ✅ 표(왼쪽) + 꺾은선 그래프(오른쪽)
                        left, right = st.columns([1.7, 2.2], gap="large")
    
                        with left:
                            st.markdown(
                                df.to_html(escape=False, index=False, classes="inv_hist_table"),
                                unsafe_allow_html=True,
                            )
    
                        with right:
                            # 가로: 변동사유 / 세로: 변동 후(주가)
                            chart_rows = []
    
                            # ✅ 초기주가 1점 추가
                            # - 변동 기록이 있으면: 가장 오래된 기록의 price_before가 '초기주가'
                            # - 변동 기록이 없으면: 현재주가를 초기로 표시
                            init_price = None
                            if hist:
                                oldest = hist[-1]  # hist는 최신순이라 마지막이 가장 오래됨
                                init_price = float(oldest.get("price_before", 0.0) or 0.0)
                            if init_price is None:
                                init_price = float(p.get("current_price", 0.0) or 0.0)
    
                            chart_rows.append({"변동사유": "시작주가", "변동 후": round(init_price, 1)})
    
                            # ✅ 이후 변동(오래된→최신)
                            for h2 in reversed(hist):
                                reason2 = str(h2.get("reason", "") or "").strip() or "-"
                                pa2 = float(h2.get("price_after", 0.0) or 0.0)
                                chart_rows.append({"변동사유": reason2, "변동 후": round(pa2, 1)})
    
                            cdf = pd.DataFrame(chart_rows)
    
                            if not cdf.empty:
                                order = cdf["변동사유"].tolist()
    
                                chart_df = cdf.copy().reset_index(drop=True)


    
                                # ✅ (PATCH) 구간별 상승/하락/보합 색상 + 점(회색) 표시

    
                                chart_df["prev_price"] = chart_df["변동 후"].shift(1)


    
                                def _dir(_row):

    
                                    p = _row.get("prev_price")

    
                                    v = _row.get("변동 후")

    
                                    if pd.isna(p) or pd.isna(v):

    
                                        return "same"

    
                                    if v > p:

    
                                        return "up"

    
                                    if v < p:

    
                                        return "down"

    
                                    return "same"


    
                                chart_df["direction"] = chart_df.apply(_dir, axis=1)

    
                                chart_df["x2"] = chart_df["변동사유"].shift(-1)

    
                                chart_df["y2"] = chart_df["변동 후"].shift(-1)

    
                                seg_df = chart_df.dropna(subset=["x2"]).copy()

                                # ✅ 구간(현재→다음) 기준으로 상승/하락/보합 판정
                                def _seg_dir(_r):
                                    y1 = _r.get("변동 후")
                                    y2 = _r.get("y2")
                                    if pd.isna(y1) or pd.isna(y2):
                                        return "same"
                                    if float(y2) > float(y1):
                                        return "up"
                                    if float(y2) < float(y1):
                                        return "down"
                                    return "same"
                                seg_df["direction_seg"] = seg_df.apply(_seg_dir, axis=1)


    
                                # ✅ (PATCH) 주가 변동 그래프: altair 없이도 항상 표시
                                try:
                                    _df = seg_df.copy()
                                    _idx_col = None
                                    for _c in ['date','time','created_at','ts','timestamp']:
                                        if _c in _df.columns:
                                            _idx_col = _c
                                            break
                                    if _idx_col:
                                        _df[_idx_col] = pd.to_datetime(_df[_idx_col], errors='coerce')
                                        _df = _df.sort_values(_idx_col).set_index(_idx_col)
                                    _price_col = None
                                    for _c in ['price','current_price','value','close','y']:
                                        if _c in _df.columns:
                                            _price_col = _c
                                            break
                                    if _price_col is None:
                                        num_cols = [c for c in _df.columns if pd.api.types.is_numeric_dtype(_df[c])]
                                        _price_col = num_cols[0] if num_cols else None
                                    if _price_col is not None:
                                        st.line_chart(_df[_price_col])
                                    else:
                                        st.info('주가 변동 데이터를 표시할 수 없어요(가격 컬럼 없음).')
                                except Exception:
                                    st.info('주가 변동 그래프를 표시하지 못했어요(데이터 형식 확인 필요).')
                    if hist:
                        rows = []
                        for h in hist:
                            dt = _ts_to_dt(h.get("created_at"))
                            pb = float(h.get("price_before", 0.0) or 0.0)
                            pa = float(h.get("price_after", 0.0) or 0.0)
                            diff = round(pa - pb, 1)
    
                            # 변동일시: 0월 0일(요일) 오전/오후 00시 00분
                            def _fmt_kor_datetime(dt_obj):
                                if not dt_obj:
                                    return "-"
                                try:
                                    dt_kst = dt_obj.astimezone(KST)
                                except Exception:
                                    dt_kst = dt_obj
    
                                hour = dt_kst.hour
                                ampm = "오전" if hour < 12 else "오후"
                                hh = hour if 1 <= hour <= 12 else (hour - 12 if hour > 12 else 12)
                                return f"{dt_kst.month}월 {dt_kst.day}일({days_ko[dt_kst.weekday()]}) {ampm} {hh:02d}시 {dt_kst.minute:02d}분"
    
                            # 주가 등락 표시 (요청: 하락은 파란 아이콘+파란 글씨)
                            if diff > 0:
                                diff_view = f"<span style='color:red'>▲ +{diff:.1f}</span>"
                            elif diff < 0:
                                diff_view = f"<span style='color:blue'>▼ {diff:.1f}</span>"
                            else:
                                diff_view = "-"
    
                            rows.append(
                                {
                                    "변동일시": _fmt_kor_datetime(dt),
                                    "변동사유": h.get("reason", "") or "",
                                    "주가": f"{pa:.1f}",          # ✅ '변동 후' → '주가'
                                    "주가 등락": diff_view,
                                }
                            )
    
                        df = pd.DataFrame(rows)
    
                        # ✅ 표(왼쪽) + 꺾은선 그래프(오른쪽)
                        left, right = st.columns([1.7,2.2], gap="large")
    
                        with left:
                            st.markdown(
                                df.to_html(escape=False, index=False, classes="inv_hist_table"),
                                unsafe_allow_html=True,
                            )
    
                        with right:
                            # 가로: 변동사유 / 세로: 변동 후(주가)
                            chart_rows = []
    
                            # ✅ 초기주가 1점 추가
                            # - 변동 기록이 있으면: 가장 오래된 기록의 price_before가 '초기주가'
                            # - 변동 기록이 없으면: 현재주가를 초기로 표시
                            init_price = None
                            if hist:
                                oldest = hist[-1]  # hist는 최신순이라 마지막이 가장 오래됨
                                init_price = float(oldest.get("price_before", 0.0) or 0.0)
                            if init_price is None:
                                init_price = float(p.get("current_price", 0.0) or 0.0)
    
                            chart_rows.append({"변동사유": "시작주가", "변동 후": round(init_price, 1)})
    
                            # ✅ 이후 변동(오래된→최신)
                            for h2 in reversed(hist):
                                reason2 = str(h2.get("reason", "") or "").strip() or "-"
                                pa2 = float(h2.get("price_after", 0.0) or 0.0)
                                chart_rows.append({"변동사유": reason2, "변동 후": round(pa2, 1)})
    
                            cdf = pd.DataFrame(chart_rows)
    
                            if not cdf.empty:
                                order = cdf["변동사유"].tolist()
    
                                chart_df = cdf.copy().reset_index(drop=True)


    
                                # ✅ (PATCH) 구간별 상승/하락/보합 색상 + 점(회색) 표시

    
                                chart_df["prev_price"] = chart_df["변동 후"].shift(1)


    
                                def _dir(_row):

    
                                    p = _row.get("prev_price")

    
                                    v = _row.get("변동 후")

    
                                    if pd.isna(p) or pd.isna(v):

    
                                        return "same"

    
                                    if v > p:

    
                                        return "up"

    
                                    if v < p:

    
                                        return "down"

    
                                    return "same"


    
                                chart_df["direction"] = chart_df.apply(_dir, axis=1)

    
                                chart_df["x2"] = chart_df["변동사유"].shift(-1)

    
                                chart_df["y2"] = chart_df["변동 후"].shift(-1)

    
                                seg_df = chart_df.dropna(subset=["x2"]).copy()

                                # ✅ 구간(현재→다음) 기준으로 상승/하락/보합 판정
                                def _seg_dir(_r):
                                    y1 = _r.get("변동 후")
                                    y2 = _r.get("y2")
                                    if pd.isna(y1) or pd.isna(y2):
                                        return "same"
                                    if float(y2) > float(y1):
                                        return "up"
                                    if float(y2) < float(y1):
                                        return "down"
                                    return "same"
                                seg_df["direction_seg"] = seg_df.apply(_seg_dir, axis=1)


    
                                # ✅ (PATCH) 주가 변동 그래프: altair 없이도 항상 표시
                                try:
                                    _df = seg_df.copy()
                                    _idx_col = None
                                    for _c in ['date','time','created_at','ts','timestamp']:
                                        if _c in _df.columns:
                                            _idx_col = _c
                                            break
                                    if _idx_col:
                                        _df[_idx_col] = pd.to_datetime(_df[_idx_col], errors='coerce')
                                        _df = _df.sort_values(_idx_col).set_index(_idx_col)
                                    _price_col = None
                                    for _c in ['price','current_price','value','close','y']:
                                        if _c in _df.columns:
                                            _price_col = _c
                                            break
                                    if _price_col is None:
                                        num_cols = [c for c in _df.columns if pd.api.types.is_numeric_dtype(_df[c])]
                                        _price_col = num_cols[0] if num_cols else None
                                    if _price_col is not None:
                                        st.line_chart(_df[_price_col])
                                    else:
                                        st.info('주가 변동 데이터를 표시할 수 없어요(가격 컬럼 없음).')
                                except Exception:
                                    st.info('주가 변동 그래프를 표시하지 못했어요(데이터 형식 확인 필요).')
    # -------------------------------------------------
    st.markdown("### 🧾 투자 상품 관리 장부")
    
    ledger_rows = _load_ledger(None if is_admin else my_student_id)
    
    view_rows = []
    for x in ledger_rows:
        redeemed = bool(x.get("redeemed", False))
        view_rows.append(
            {
                "번호": int(x.get("no", 0) or 0),
                "이름": str(x.get("name", "") or ""),
                "종목": str(x.get("product_name", "") or ""),
                "매입일자": str(x.get("buy_date_label", "") or ""),
                "매입 주가": f"{_as_price1(x.get('buy_price', 0.0)):.1f}",
                "투자 금액": int(x.get("invest_amount", 0) or 0),
                "지급완료": "✅" if redeemed else "",
                "매수일자": str(x.get("sell_date_label", "") or ""),
                "매수 주가": f"{_as_price1(x.get('sell_price', 0.0)):.1f}" if redeemed else "",
                "주가차이": f"{_as_price1(x.get('diff', 0.0)):.1f}" if redeemed else "",
                "수익/손실금": int(round(float(x.get("profit", 0.0) or 0.0))) if redeemed else "",
                "찾을 금액": int(x.get("redeem_amount", 0) or 0) if redeemed else "",
                "_doc_id": x.get("_doc_id"),
                "_student_id": x.get("student_id"),
                "_product_id": x.get("product_id"),
                "_buy_price": x.get("buy_price"),
                "_invest_amount": x.get("invest_amount"),
            }
        )
    
    if view_rows:
        st.dataframe(pd.DataFrame(view_rows).drop(columns=["_doc_id","_student_id","_product_id","_buy_price","_invest_amount"], errors="ignore"),
                     use_container_width=True, hide_index=True)
    else:
        st.caption("투자 내역이 없습니다.")
    
    # -------------------------------------------------
    # 2-1) 지급(회수) 처리
    # -------------------------------------------------
    pending = [x for x in view_rows if not any([x.get("지급완료") == "✅"])]
    if pending:
        st.markdown("#### 💸 투자 회수(지급)")
        can_redeem_now = _can_redeem(my_student_id)
        if (not is_admin) and (not can_redeem_now):
            st.info("투자 회수는 관리자 또는 '투자증권' 직업 학생만 할 수 있어요.")
        else:
            for x in pending[:100]:
                doc_id = str(x.get("_doc_id", "") or "")
                sid = str(x.get("_student_id", "") or "")
                pid = str(x.get("_product_id", "") or "")
                buy_price = _as_price1(x.get("_buy_price", 0.0))
                invest_amt = int(x.get("_invest_amount", 0) or 0)
                prod_name = str(x.get("종목", "") or "")
    
                # 현재 주가 찾기
                cur_price = buy_price
                for p in products:
                    if str(p["product_id"]) == pid:
                        cur_price = _as_price1(p["current_price"])
                        break
    
                diff, profit, redeem_amt = _calc_redeem_amount(invest_amt, buy_price, cur_price)
    
                c1, c2, c3, c4 = st.columns([1.2, 2.2, 2.8, 1.2], gap="small")
                with c1:
                    st.markdown(f"**{x.get('번호','')}**")
                with c2:
                    st.markdown(f"{x.get('이름','')}")
                    st.caption(prod_name)
                with c3:
                    st.caption(f"매입 {buy_price:.1f} → 현재 {cur_price:.1f} (차이 {diff:.1f})")
                    st.caption(f"수익/손실 {profit:.1f} | 찾을 금액 {redeem_amt}")
                with c4:
                    if st.button("지급", use_container_width=True, key=f"inv_pay_{doc_id}"):
    
                        sell_dt = datetime.now(tz=KST)
                        sell_label = _fmt_kor_date_md(sell_dt)
                        memo = f"투자 회수({prod_name})"
    
                        if inv_admin_ok:
                            res = api_admin_add_tx_by_student_id(
                                admin_pin=ADMIN_PIN,
                                student_id=sid,
                                memo=memo,
                                deposit=int(redeem_amt),
                                withdraw=0,
                            )
                        else:
                            res = api_broker_deposit_by_student_id(
                                actor_student_id=my_student_id,
                                student_id=sid,
                                memo=memo,
                                deposit=int(redeem_amt),
                            )
    
                        if res.get("ok"):
                            try:
                                db.collection(INV_LEDGER_COL).document(doc_id).set(
                                    {
                                        "redeemed": True,
                                        "sell_at": firestore.SERVER_TIMESTAMP,
                                        "sell_date_label": sell_label,
                                        "sell_price": _as_price1(cur_price),
                                        "diff": _as_price1(diff),
                                        "profit": float(profit),
                                        "redeem_amount": int(redeem_amt),
                                    },
                                    merge=True,
                                )
                                toast("지급 완료!", icon="✅")
                                st.rerun()
                            except Exception as e:
                                st.error(f"장부 업데이트 실패: {e}")
                        else:
                            st.error(res.get("error", "지급 실패"))
    
    st.divider()
    
    # -------------------------------------------------
    # 3) (사용자) 투자 실행
    # -------------------------------------------------
    if not is_admin:
        st.markdown("### 💳 투자하기")
    
        inv_ok2 = True
        try:
            snap = db.collection("students").document(str(my_student_id)).get()
            if snap.exists:
                inv_ok2 = bool((snap.to_dict() or {}).get("invest_enabled", True))
        except Exception:
            inv_ok2 = True
    
        if not inv_ok2:
            st.warning("이 계정은 현재 투자 기능이 비활성화되어 있어요.")
        elif not products:
            st.info("투자 종목이 아직 없어요. 관리자에게 종목 추가를 요청해 주세요.")
        else:
            prod_labels = [f"{p['name']} (현재 {p['current_price']:.1f})" for p in products]
            by_label = {lab: p for lab, p in zip(prod_labels, products)}
    
            sel_lab = st.selectbox("투자 종목 선택", prod_labels, key="inv_user_sel_prod")
            sel_prod = by_label.get(sel_lab)
    
            amt = st.number_input("투자 금액", min_value=0, step=10, value=0, key="inv_user_amt")
            if st.button("투자(다음 확인창에서 ‘예’를 눌러야 완료, 신중하게 결정하기)", use_container_width=True, key="inv_user_btn"):
                if int(amt) <= 0:
                    st.warning("투자 금액을 입력해 주세요.")
                else:
                    st.session_state["inv_user_confirm"] = True
    
            if st.session_state.get("inv_user_confirm", False):
                st.warning("정말로 투자할까요?")
                y, n = st.columns(2)
                with y:
                    if st.button("예", use_container_width=True, key="inv_user_yes"):
                        st.session_state["inv_user_confirm"] = False
    
                        memo = f"투자 매입({sel_prod['name']})"
                        res = api_add_tx(login_name, login_pin, memo=memo, deposit=0, withdraw=int(amt))
                        if res.get("ok"):
                            try:
                                sd = fs_auth_student(login_name, login_pin)
                                sdata = sd.to_dict() or {}
                                no = int(sdata.get("no", 0) or 0)
    
                                buy_dt = datetime.now(tz=KST)
                                buy_label = _fmt_kor_date_md(buy_dt)
    
                                db.collection(INV_LEDGER_COL).document().set(
                                    {
                                        "student_id": sd.id,
                                        "no": no,
                                        "name": str(sdata.get("name", "") or ""),
                                        "product_id": sel_prod["product_id"],
                                        "product_name": sel_prod["name"],
                                        "buy_at": firestore.SERVER_TIMESTAMP,
                                        "buy_date_label": buy_label,
                                        "buy_price": _as_price1(sel_prod["current_price"]),
                                        "invest_amount": int(amt),
                                        "redeemed": False,
                                    }
                                )
                                toast("투자 완료! (장부에 반영됨)", icon="✅")
                                st.rerun()
                            except Exception as e:
                                st.error(f"장부 저장 실패: {e}")
                        else:
                            st.error(res.get("error", "투자 실패"))
                with n:
                    if st.button("아니오", use_container_width=True, key="inv_user_no"):
                        st.session_state["inv_user_confirm"] = False
                        st.rerun()
    
    # -------------------------------------------------
    # 4) (관리자) 투자 종목 추가/수정/삭제
    # -------------------------------------------------
    if inv_admin_ok:
        st.divider()
        st.markdown("### 🧰 투자 종목 추가/수정/삭제")
    
        prod_all = _get_products(active_only=False)
    
        # ✅ 드롭다운에는 "활성 종목"만 보이게(삭제=비활성은 숨김)
        prod_active = [p for p in prod_all if bool(p.get("is_active", True))]
    
        labels = ["(신규 추가)"] + [p["name"] for p in prod_active if p["name"]]
    
        sel = st.selectbox("편집 대상", labels, key="inv_admin_edit_sel")
    
        cur_obj = None
        if sel != "(신규 추가)":
            for p in prod_active:
                if p["name"] == sel:
                    cur_obj = p
                    break
    
        name_default = "" if cur_obj is None else cur_obj["name"]
        price_default = 0.0 if cur_obj is None else float(cur_obj["current_price"])
    
        c1, c2 = st.columns([2.2, 1.2], gap="small")
        with c1:
            new_name = st.text_input("투자 종목명", value=name_default, key="inv_admin_name")
        with c2:
            new_price = st.number_input(
                "초기/현재 주가",
                min_value=0.0,
                max_value=999.9,
                step=0.1,
                format="%.1f",
                value=float(price_default),
                key="inv_admin_price",
            )
    
        b1, b2 = st.columns(2)
        with b1:
            if st.button("저장", use_container_width=True, key="inv_admin_save"):
                nm = str(new_name or "").strip()
                if not nm:
                    st.warning("종목명을 입력해 주세요.")
                else:
                    # ✅ 중복 종목명 방지(공백/대소문자 무시)
                    nm_key = nm.replace(" ", "").lower()
                    dup = None
                    for p in prod_all:
                        pnm = str(p.get("name", "") or "").strip()
                        if pnm and pnm.replace(" ", "").lower() == nm_key:
                            dup = p
                            break
    
                    # (신규 추가)인데 이미 존재하면:
                    # - 활성 종목이면: 중복 추가 막기
                    # - 비활성(삭제된) 종목이면: 새로 만들지 말고 "복구(재활성화)" 처리
                    if cur_obj is None and dup is not None:
                        if bool(dup.get("is_active", True)):
                            st.error("이미 같은 종목명이 있어요. (중복 추가 불가)")
                            st.stop()
                        else:
                            # ✅ 비활성 종목 복구
                            try:
                                db.collection(INV_PROD_COL).document(dup["product_id"]).set(
                                    {
                                        "name": nm,
                                        "current_price": _as_price1(new_price),
                                        "is_active": True,
                                        "updated_at": firestore.SERVER_TIMESTAMP,
                                    },
                                    merge=True,
                                )
                                toast("삭제된 종목을 복구했습니다.", icon="♻️")
                                st.rerun()
                            except Exception as e:
                                st.error(f"복구 실패: {e}")
                                st.stop()
    
                    # (수정)인데 다른 문서와 이름이 겹치면 막기
                    if cur_obj is not None and dup is not None and str(dup.get("product_id")) != str(cur_obj.get("product_id")):
                        st.error("이미 같은 종목명이 있어요. (중복 이름 불가)")
                        st.stop()
    
                    try:
                        if cur_obj is None:
                            db.collection(INV_PROD_COL).document().set(
                                {
                                    "name": nm,
                                    "current_price": _as_price1(new_price),
                                    "is_active": True,
                                    "created_at": firestore.SERVER_TIMESTAMP,
                                    "updated_at": firestore.SERVER_TIMESTAMP,
                                }
                            )
                            toast("종목이 추가되었습니다.", icon="✅")
                        else:
                            db.collection(INV_PROD_COL).document(cur_obj["product_id"]).set(
                                {
                                    "name": nm,
                                    "current_price": _as_price1(new_price),
                                    "is_active": True,
                                    "updated_at": firestore.SERVER_TIMESTAMP,
                                },
                                merge=True,
                            )
                            toast("종목이 수정되었습니다.", icon="✅")
                        st.rerun()
                    except Exception as e:
                        st.error(f"저장 실패: {e}")
        with b2:
            if st.button("삭제", use_container_width=True, key="inv_admin_del", disabled=(cur_obj is None)):
                if cur_obj is None:
                    st.stop()
                try:
                    db.collection(INV_PROD_COL).document(cur_obj["product_id"]).set(
                        {"is_active": False, "updated_at": firestore.SERVER_TIMESTAMP},
                        merge=True,
                    )
                    toast("삭제(비활성화) 완료", icon="🗑️")
                    st.rerun()
                except Exception as e:
                    st.error(f"삭제 실패: {e}")
    
    # =========================
    # 👥 계정 정보/활성화 (관리자 전용)
    # =========================



# (PATCH) 아래 구간은 class 앱에서 가져오다 중복/오염된 'tabs/tab_map' 기반 렌더링 블록이라 제거했습니다.
#        house 앱에서는 하단의 _render_jobs_admin_like(), _render_invest_admin_like() 등을
#        '관리자 st.tabs(...)' / '사용자 화면'에서 직접 호출하는 구조만 사용합니다.

def _render_jobs_admin_like():
    st.subheader("💼 직업/월급 시스템")


    # -------------------------------------------------
    # ✅ 계정 목록(드롭다운: 번호+이름)
    # -------------------------------------------------
    accounts = api_list_accounts_cached().get("accounts", [])
    # students 컬렉션에서 'no'도 같이 가져와서 "번호+이름" 만들기
    docs_acc = db.collection("students").where(filter=FieldFilter("is_active", "==", True)).stream()
    acc_rows = []
    for d in docs_acc:
        x = d.to_dict() or {}
        try:
            no = int(x.get("no", 999999) or 999999)
        except Exception:
            no = 999999
        acc_rows.append(
            {
                "student_id": d.id,
                "no": no,
                "name": str(x.get("name", "") or ""),
            }
        )
    acc_rows.sort(key=lambda r: (r["no"], r["name"]))

    # ✅ (PATCH) 드롭다운 라벨에서 '999999' 같은 번호를 화면에 표시하지 않음
    # - 기본은 이름만 표시
    # - 이름이 중복되면 뒤에 ·2, ·3 처럼 자동으로 구분 라벨을 붙임
    name_counts = {}
    acc_labels = []
    label_to_id = {}
    for r in acc_rows:
        nm = str(r.get("name","") or "").strip()
        if not nm:
            nm = "(이름 없음)"
        c = name_counts.get(nm, 0) + 1
        name_counts[nm] = c
        lab = nm if c == 1 else f"{nm} ·{c}"
        acc_labels.append(lab)
        label_to_id[lab] = r["student_id"]

    acc_options = ["(선택 없음)"] + acc_labels

    # (PATCH) id_to_label 제거: 화면 표기는 이름만 사용합니다.

    # -------------------------------------------------
    # ✅ 공제 설정(세금% / 자리임대료 / 전기세 / 건강보험료)
    #   - Firestore config/salary_deductions 에 저장
    # -------------------------------------------------
    def _get_salary_cfg():
        ref = db.collection("config").document("salary_deductions")
        snap = ref.get()
        if not snap.exists:
            return {
                "tax_percent": 10.0,
                "desk_rent": 50,
                "electric_fee": 10,
                "health_fee": 10,
            }
        d = snap.to_dict() or {}
        return {
            "tax_percent": float(d.get("tax_percent", 10.0) or 10.0),
            "desk_rent": int(d.get("desk_rent", 50) or 50),
            "electric_fee": int(d.get("electric_fee", 10) or 10),
            "health_fee": int(d.get("health_fee", 10) or 10),
        }

    def _save_salary_cfg(cfg: dict):
        db.collection("config").document("salary_deductions").set(
            {
                "tax_percent": float(cfg.get("tax_percent", 10.0) or 10.0),
                "desk_rent": int(cfg.get("desk_rent", 50) or 50),
                "electric_fee": int(cfg.get("electric_fee", 10) or 10),
                "health_fee": int(cfg.get("health_fee", 10) or 10),
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

    def _calc_net(gross: int, cfg: dict) -> int:
        gross = int(gross or 0)
        tax_percent = float(cfg.get("tax_percent", 10.0) or 10.0)
        desk = int(cfg.get("desk_rent", 50) or 50)
        elec = int(cfg.get("electric_fee", 10) or 10)
        health = int(cfg.get("health_fee", 10) or 10)

        tax = int(round(gross * (tax_percent / 100.0)))
        net = gross - tax - desk - elec - health
        return max(0, int(net))

    cfg = _get_salary_cfg()

    with st.expander("⚙️ 실수령액 계산식(공제 설정) 변경", expanded=False):
        c1, c2, c3, c4, c5 = st.columns([1.2, 1, 1, 1, 1.2])
        with c1:
            tax_percent = st.number_input("세금(%)", min_value=0.0, max_value=100.0, step=0.5, value=float(cfg["tax_percent"]), key="sal_cfg_tax")
        with c2:
            desk_rent = st.number_input("자리임대료", min_value=0, step=1, value=int(cfg["desk_rent"]), key="sal_cfg_desk")
        with c3:
            electric_fee = st.number_input("전기세", min_value=0, step=1, value=int(cfg["electric_fee"]), key="sal_cfg_elec")
        with c4:
            health_fee = st.number_input("건강보험료", min_value=0, step=1, value=int(cfg["health_fee"]), key="sal_cfg_health")
        with c5:
            if st.button("✅ 공제 설정 저장", use_container_width=True, key="sal_cfg_save"):
                _save_salary_cfg(
                    {
                        "tax_percent": tax_percent,
                        "desk_rent": desk_rent,
                        "electric_fee": electric_fee,
                        "health_fee": health_fee,
                    }
                )
                toast("공제 설정 저장 완료!", icon="✅")
                st.rerun()

            # -------------------------------------------------
    # ✅ 월급 지급 설정(자동/수동)
    #  - config/salary_payroll : pay_day(1~31), auto_enabled(bool)
    #  - payroll_log/{YYYY-MM}_{student_id} 로 "이번달 지급 여부" 기록
    # -------------------------------------------------
    def _get_payroll_cfg():
        ref = db.collection("config").document("salary_payroll")
        snap = ref.get()
        if not snap.exists:
            return {"pay_day": 17, "auto_enabled": False}
        d = snap.to_dict() or {}
        return {
            "pay_day": int(d.get("pay_day", 25) or 25),
            "auto_enabled": bool(d.get("auto_enabled", False)),
        }

    def _save_payroll_cfg(cfg2: dict):
        db.collection("config").document("salary_payroll").set(
            {
                "pay_day": int(cfg2.get("pay_day", 25) or 25),
                "auto_enabled": bool(cfg2.get("auto_enabled", False)),
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

    def _month_key(dt: datetime) -> str:
        return f"{dt.year:04d}-{dt.month:02d}"

    def _paylog_id(month_key: str, student_id: str, job_id: str = "") -> str:
        # ✅ 월급 지급 로그는 '학생당 1개'가 아니라 '학생+직업당 1개'로 기록
        job_id = str(job_id or "").strip() or "_"
        return f"{month_key}_{student_id}_{job_id}"

    def _already_paid_this_month(month_key: str, student_id: str, job_id: str = "", job_name: str = "") -> bool:
        """이번 달 해당 학생/해당 직업에 대해 이미 월급이 지급되었는지 확인
        - 신규: payroll_log/{YYYY-MM}_{studentId}_{jobId}
        - 레거시(호환): payroll_log/{YYYY-MM}_{studentId} 가 있으면, 저장된 job 이름이 같을 때만 True
        """
        # 1) 신규 키
        snap = db.collection("payroll_log").document(_paylog_id(month_key, student_id, job_id)).get()
        if bool(snap.exists):
            return True

        # 2) 레거시 키(기존 데이터 호환)
        legacy_id = f"{month_key}_{student_id}"
        legacy = db.collection("payroll_log").document(legacy_id).get()
        if legacy.exists:
            ld = legacy.to_dict() or {}
            legacy_job = str(ld.get("job", "") or "")
            # 레거시는 "학생당 1개"로 덮어쓰던 구조였으므로,
            # 현재 지급하려는 직업과 이름이 같을 때만 '지급됨'으로 간주
            if legacy_job and (legacy_job == str(job_name or "")):
                return True
        return False

    def _write_paylog(month_key: str, student_id: str, amount: int, job_name: str, method: str, job_id: str = ""):
        db.collection("payroll_log").document(_paylog_id(month_key, student_id, job_id)).set(
            {
                "month": month_key,
                "student_id": student_id,
                "amount": int(amount),
                "job": str(job_name or ""),
                "job_id": str(job_id or ""),
                "method": str(method or ""),  # "auto" / "manual"
                "paid_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

    def _pay_one_student(student_id: str, amount: int, memo: str):
        # 관리자 지급으로 통장 입금(+)
        return api_admin_add_tx_by_student_id(
            admin_pin=ADMIN_PIN,
            student_id=student_id,
            memo=memo,
            deposit=int(amount),
            withdraw=0,
        )

    def _run_auto_payroll_if_due(cfg_pay: dict):
        # ✅ 자동지급: 매월 지정일에만 실행
        if not bool(cfg_pay.get("auto_enabled", False)):
            return

        now = datetime.now(KST)
        pay_day = int(cfg_pay.get("pay_day", 25) or 25)
        pay_day = max(1, min(31, pay_day))

        if int(now.day) != pay_day:
            return

        mkey = _month_key(now)

        # 학생 id -> 이름 맵 (메모용)
        accs = api_list_accounts_cached().get("accounts", []) or []
        id_to_name = {a.get("student_id"): a.get("name") for a in accs if a.get("student_id")}

        # job_salary 기준으로 배정된 학생들에게 지급
        q = db.collection("job_salary").order_by("order").stream()
        paid_cnt, skip_cnt, err_cnt = 0, 0, 0

        for d in q:
            x = d.to_dict() or {}
            job_id = str(d.id)
            job_name = str(x.get("job", "") or "")
            gross = int(x.get("salary", 0) or 0)
            net_amt = int(_calc_net(gross, cfg) or 0)
            assigned_ids = list(x.get("assigned_ids", []) or [])

            if net_amt <= 0:
                continue

            for sid in assigned_ids:
                sid = str(sid or "").strip()
                if not sid:
                    continue

                # ✅ 이번 달에 수동/자동 지급 기록이 있으면 자동 지급은 패스
                if _already_paid_this_month(mkey, sid, job_id=job_id, job_name=job_name):
                    skip_cnt += 1
                    continue

                nm = id_to_name.get(sid, "")
                memo = f"월급 {job_name}"
                res = _pay_one_student(sid, net_amt, memo)
                                    # ✅ (국고 세입) 월급 공제액을 국고로 입금
                deduction = int(max(0, gross - net_amt))
                if deduction > 0:
                    api_add_treasury_tx(
                        admin_pin=ADMIN_PIN,
                        memo=f"월급 공제 세입({mkey}) {job_name}" + (f" - {nm}" if nm else ""),
                        income=deduction,
                        expense=0,
                        actor="system_salary",
                    )
                if res.get("ok"):
                    _write_paylog(mkey, sid, net_amt, job_name, method="auto", job_id=job_id)
                    paid_cnt += 1
                else:
                    err_cnt += 1

        # 자동지급 결과는 너무 시끄럽지 않게 토스트 1번만
        if paid_cnt > 0:
            toast(f"월급 자동지급 완료: {paid_cnt}명(패스 {skip_cnt})", icon="💸")
            api_list_accounts_cached.clear()
        elif err_cnt > 0:
            st.warning("월급 자동지급 중 일부 오류가 있었어요. (로그 확인)")

    payroll_cfg = _get_payroll_cfg()

    # ✅ 자동지급 조건이면 즉시 한번 실행(해당 날짜일 때만 실제 지급됨)
    _run_auto_payroll_if_due(payroll_cfg)

    with st.expander("💸 월급 지급 설정", expanded=False):
        cc1, cc2, cc3 = st.columns([1.4, 1.2, 1.4])

        with cc1:
            pay_day_in = st.number_input(
                "월급 지급 날짜 지정: 매월 (일)",
                min_value=1,
                max_value=31,
                step=1,
                value=int(payroll_cfg.get("pay_day", 25) or 25),
                key="payroll_day_in",
            )

        with cc2:
            auto_on = st.checkbox(
                "자동지급",
                value=bool(payroll_cfg.get("auto_enabled", False)),
                key="payroll_auto_on",
                help="해당 날짜에 매월, 학생의 직업 실수령액 기준으로 자동 지급합니다.\n이미 이번 달에 수동지급을 했으면 자동지급은 그 달에는 패스됩니다.",
            )

        with cc3:
            if st.button("✅ 지급 설정 저장", use_container_width=True, key="payroll_save_cfg"):
                _save_payroll_cfg({"pay_day": int(pay_day_in), "auto_enabled": bool(auto_on)})
                toast("월급 지급 설정 저장 완료!", icon="✅")
                st.rerun()

        st.caption("• 수동지급: 이번 달(현재 월)에 즉시 지급합니다. 이미 지급한 기록이 있으면 확인 후 재지급합니다.")

        # -------------------------
        # 수동지급 버튼 + 이미 지급 여부 확인(이번 달)
        # -------------------------
        now = datetime.now(KST)
        cur_mkey = _month_key(now)

        # 이번 달에 지급된 로그가 있는지 빠르게 확인
        # (수동지급은 '모든 배정 학생' 대상으로 동일 로직)
        q2 = db.collection("job_salary").order_by("order").stream()
        targets = []  # (student_id, amount, job_name)
        for d in q2:
            x = d.to_dict() or {}
            job_name = str(x.get("job", "") or "")
            gross = int(x.get("salary", 0) or 0)
            net_amt = int(_calc_net(gross, cfg) or 0)
            if net_amt <= 0:
                continue
            for sid in list(x.get("assigned_ids", []) or []):
                sid = str(sid or "").strip()
                if sid:
                    targets.append((sid, net_amt, job_name, gross, str(d.id)))
        # ✅ 여러 직업 배정 허용: (학생+직업) 단위로 각각 지급

        already_any = any(_already_paid_this_month(cur_mkey, sid, job_id=jid, job_name=jb) for sid, _, jb, _, jid in targets)

        if st.button("💸 수동지급(이번 달 즉시 지급)", use_container_width=True, key="payroll_manual_btn"):
            # 이미 지급된 적 있으면 확인창 띄우기
            if already_any:
                st.session_state["payroll_manual_confirm"] = True
            else:
                st.session_state["payroll_manual_confirm"] = False
                st.session_state["payroll_manual_do"] = True
            st.rerun()

        if st.session_state.get("payroll_manual_confirm", False):
            st.warning("이번 달에 이미 월급 지급(자동/수동)한 기록이 있습니다. 그래도 지급하시겠습니까?")
            y1, n1 = st.columns(2)
            with y1:
                if st.button("예", use_container_width=True, key="payroll_manual_yes"):
                    st.session_state["payroll_manual_confirm"] = False
                    st.session_state["payroll_manual_do"] = True
                    st.rerun()
            with n1:
                if st.button("아니오", use_container_width=True, key="payroll_manual_no"):
                    st.session_state["payroll_manual_confirm"] = False
                    st.session_state["payroll_manual_do"] = False
                    toast("수동지급 취소", icon="🛑")
                    st.rerun()

        # 실제 수동지급 실행(1회)
        if st.session_state.get("payroll_manual_do", False):
            st.session_state["payroll_manual_do"] = False

            accs2 = api_list_accounts_cached().get("accounts", []) or []
            id_to_name2 = {a.get("student_id"): a.get("name") for a in accs2 if a.get("student_id")}

            paid_cnt, err_cnt = 0, 0
            for sid, amt, jb, gross, job_id2 in targets:
                nm = id_to_name2.get(sid, "")
                memo = f"월급 {jb}"
                res = _pay_one_student(sid, int(amt), memo)
                # ✅ (국고 세입) 월급 공제액을 국고로 입금
                deduction = int(max(0, int(gross) - int(amt))) if "gross" in locals() else 0
                if deduction > 0:
                    api_add_treasury_tx(
                        admin_pin=ADMIN_PIN,
                        memo=f"월급 공제 세입({cur_mkey}) {jb}" + (f" - {nm}" if nm else ""),
                        income=deduction,
                        expense=0,
                        actor="system_salary",
                    )

                if res.get("ok"):
                    # ✅ 수동지급도 이번달 지급 기록 남김(자동 패스 조건 충족)
                    _write_paylog(cur_mkey, sid, int(amt), jb, method="manual", job_id=job_id2)
                    paid_cnt += 1
                else:
                    err_cnt += 1

            api_list_accounts_cached.clear()
            if paid_cnt > 0:
                toast(f"월급 수동지급 완료: {paid_cnt}명", icon="💸")
            if err_cnt > 0:
                st.warning(f"일부 지급 실패가 있었어요: {err_cnt}건")
            st.rerun()

    # -------------------------------------------------
    # ✅ 직업/월급 데이터 로드 (job_salary 컬렉션)
    #   - student_count(정원) 관련 필드는 '호환용으로만' 남기고, 이 화면/로직에서는 사용하지 않습니다(무제한).
    # -------------------------------------------------
    def _list_job_rows():
        q = db.collection("job_salary").order_by("order").stream()
        rows = []
        for d in q:
            x = d.to_dict() or {}
            rows.append(
                {
                    "_id": d.id,
                    "order": int(x.get("order", 999999) or 999999),
                    "job": str(x.get("job", "") or ""),
                    "salary": int(x.get("salary", 0) or 0),
                    # 호환용(미사용)
                    "student_count": int(x.get("student_count", 0) or 0),
                    "assigned_ids": [str(sid) for sid in (x.get("assigned_ids", []) or []) if str(sid).strip()],
                }
            )
        rows.sort(key=lambda r: r["order"])
        return rows

    def _next_order(rows):
        if not rows:
            return 1
        return int(max(r["order"] for r in rows) + 1)

    def _swap_order(a_id, a_order, b_id, b_order):
        batch = db.batch()
        batch.update(db.collection("job_salary").document(a_id), {"order": int(b_order)})
        batch.update(db.collection("job_salary").document(b_id), {"order": int(a_order)})
        batch.commit()

    rows = _list_job_rows()

    # -------------------------------------------------
    # ✅ 직업 지정 / 회수 (무제한 배정)
    # -------------------------------------------------
    st.markdown("### 🎖️ 직업 지정 / 회수")
    st.caption("직업을 선택한 뒤, 학생을 선택하고 ‘고용/해제’ 버튼을 누르세요. (정원 제한 없음)")

    job_pick_labels = [f"{r['order']} | {r['job']} (월급 {int(r['salary'])})" for r in rows]
    job_pick_map = {lab: r["_id"] for lab, r in zip(job_pick_labels, rows)}

    a1, a2 = st.columns([1.2, 2.0])
    with a1:
        sel_job_label = st.selectbox("부여할 직업 선택", job_pick_labels, key="job_assign_pick2") if job_pick_labels else None
    with a2:
        sel_students_labels = st.multiselect(
            "대상 학생 선택(복수 선택 가능)",
            [lab for lab in acc_options if lab != "(선택 없음)"],
            key="job_assign_students2",
        )

    b1, b2 = st.columns([1, 1])
    with b1:
        if st.button("➕ 고용", use_container_width=True, key="job_assign_hire_btn2"):
            if not sel_job_label:
                st.warning("먼저 직업을 선택하세요.")
            elif not sel_students_labels:
                st.warning("대상 학생을 선택하세요.")
            else:
                rid = job_pick_map.get(sel_job_label)
                if rid:
                    ref = db.collection("job_salary").document(rid)
                    snap = ref.get()
                    if snap.exists:
                        x = snap.to_dict() or {}
                        assigned = [str(sid) for sid in (x.get("assigned_ids", []) or []) if str(sid).strip()]
                        changed = False
                        for lab in sel_students_labels:
                            sid = str(label_to_id.get(lab, "") or "").strip()
                            if not sid:
                                continue
                            if sid in assigned:
                                continue
                            assigned.append(sid)
                            changed = True

                        if changed:
                            ref.update({"assigned_ids": assigned, "student_count": 0})
                            toast("고용 완료!", icon="✅")
                            api_list_accounts_cached.clear()
                            st.rerun()
                        else:
                            st.info("변경된 내용이 없습니다. (이미 배정됨)")
    with b2:
        if st.button("➖ 해제", use_container_width=True, key="job_assign_fire_btn2"):
            if not sel_job_label:
                st.warning("먼저 직업을 선택하세요.")
            elif not sel_students_labels:
                st.warning("대상 학생을 선택하세요.")
            else:
                rid = job_pick_map.get(sel_job_label)
                if rid:
                    ref = db.collection("job_salary").document(rid)
                    snap = ref.get()
                    if snap.exists:
                        x = snap.to_dict() or {}
                        assigned = [str(sid) for sid in (x.get("assigned_ids", []) or []) if str(sid).strip()]
                        sel_ids = [str(label_to_id.get(lab, "") or "").strip() for lab in sel_students_labels]
                        sel_ids = [sid for sid in sel_ids if sid]
                        new_assigned = [sid for sid in assigned if sid not in sel_ids]
                        if new_assigned != assigned:
                            ref.update({"assigned_ids": new_assigned, "student_count": 0})
                            toast("해제 완료!", icon="✅")
                            api_list_accounts_cached.clear()
                            st.rerun()
                        else:
                            st.info("해제할 배정이 없습니다.")

    # -------------------------------------------------
    # ✅ 전체 직업 해제
    # -------------------------------------------------
    c1, c2 = st.columns([1.0, 2.0])
    with c1:
        all_clear_chk = st.checkbox("전체 직업 해제", value=False, key="job_assign_clear_all_chk")
    with c2:
        if st.button("🔥 전체 직업 해제", use_container_width=True, key="job_assign_clear_all_btn", disabled=(not bool(all_clear_chk))):
            try:
                _rows2 = _list_job_rows()
                batch = db.batch()
                for rr in _rows2:
                    batch.update(db.collection("job_salary").document(rr["_id"]), {"assigned_ids": [], "student_count": 0})
                batch.commit()
                toast("전체 직업 해제 완료!", icon="✅")
                api_list_accounts_cached.clear()
                st.rerun()
            except Exception as e:
                st.error(f"전체 직업 해제 실패: {e}")

    st.divider()

    # -------------------------------------------------
    # ✅ 직업 현황(학생 기준 표) — 배정된 학생만 표시
    # -------------------------------------------------
    st.markdown("### 📋 직업/월급 목록")
    status_rows = []
    id_to_no_name = {r["student_id"]: (r["no"], r["name"]) for r in acc_rows}

    for r in rows:
        job = r["job"]
        salary = int(r["salary"])
        net = int(_calc_net(salary, cfg) or 0)
        for sid in (r.get("assigned_ids", []) or []):
            sid = str(sid).strip()
            if not sid:
                continue
            no, nm = id_to_no_name.get(sid, (999999, ""))
            status_rows.append({"번호": int(no) if str(no).isdigit() else no, "이름": nm, "직업": job, "월급": salary, "실수령액": net})

    if status_rows:
        df_status = pd.DataFrame(status_rows)
        try:
            df_status["번호_정렬"] = pd.to_numeric(df_status["번호"], errors="coerce").fillna(999999).astype(int)
            df_status = df_status.sort_values(["번호_정렬", "이름", "직업"], kind="mergesort").drop(columns=["번호_정렬"])
        except Exception:
            df_status = df_status.sort_values(["번호", "이름", "직업"], kind="mergesort")
        st.dataframe(df_status[["번호", "이름", "직업", "월급", "실수령액"]], use_container_width=True, hide_index=True)
    else:
        st.info("아직 직업이 배정된 학생이 없습니다.")

    st.divider()

    # -------------------------------------------------
    # ✅ 직업 추가 / 수정 / 삭제 / 순서 이동 (정원 제한 없음)
    # -------------------------------------------------
    st.markdown("### ➕ 직업 추가 / 수정")

    pick_labels = ["(새로 추가)"] + [f"{r['order']} | {r['job']} (월급 {int(r['salary'])})" for r in rows]
    picked = st.selectbox("편집 대상", pick_labels, key="job_edit_pick")

    edit_row = None
    if picked != "(새로 추가)":
        for rr in rows:
            lab = f"{rr['order']} | {rr['job']} (월급 {int(rr['salary'])})"
            if lab == picked:
                edit_row = rr
                break

    f1, f2, f3 = st.columns([2.2, 1.2, 1.2])
    with f1:
        job_in = st.text_input("직업", value=(edit_row["job"] if edit_row else ""), key="job_in_job").strip()
    with f2:
        sal_in = st.number_input("월급", min_value=0, step=1, value=int(edit_row["salary"]) if edit_row else 0, key="job_in_salary")
    with f3:
        st.metric("실수령액(자동)", _calc_net(int(sal_in), cfg))

    cbtn1, cbtn2, cbtn3 = st.columns([1, 1, 1])
    with cbtn1:
        if st.button("✅ 저장", use_container_width=True, key="job_save_btn"):
            if not job_in:
                st.error("직업을 입력해 주세요.")
                st.stop()

            if edit_row:
                rid = edit_row["_id"]
                cur_ids = [str(sid) for sid in (edit_row.get("assigned_ids", []) or []) if str(sid).strip()]
                db.collection("job_salary").document(rid).update(
                    {
                        "job": job_in,
                        "salary": int(sal_in),
                        "student_count": 0,
                        "assigned_ids": cur_ids,
                        "updated_at": firestore.SERVER_TIMESTAMP,
                    }
                )
                toast("수정 완료!", icon="✅")
            else:
                new_order = _next_order(rows)
                db.collection("job_salary").document().set(
                    {
                        "order": int(new_order),
                        "job": job_in,
                        "salary": int(sal_in),
                        "student_count": 0,
                        "assigned_ids": [],
                        "created_at": firestore.SERVER_TIMESTAMP,
                    }
                )
                toast("추가 완료!", icon="✅")

            api_list_accounts_cached.clear()
            st.rerun()

    with cbtn2:
        if st.button("🗑️ 삭제", use_container_width=True, key="job_del_btn", disabled=(edit_row is None)):
            if edit_row:
                try:
                    db.collection("job_salary").document(edit_row["_id"]).delete()
                    toast("삭제 완료!", icon="✅")
                    api_list_accounts_cached.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"삭제 실패: {e}")

    with cbtn3:
        if st.button("🔼/🔽 순서 조정", use_container_width=True, key="job_order_btn", disabled=(edit_row is None)):
            st.info("아래에서 위/아래로 이동할 직업을 선택해 주세요.")

    if edit_row:
        o1, o2 = st.columns([1, 1])
        with o1:
            if st.button("🔼 위로", use_container_width=True, key="job_move_up_btn"):
                # 현재 직업의 바로 위 job 찾기
                cur = edit_row
                above = None
                for rr in rows:
                    if rr["order"] < cur["order"]:
                        above = rr
                if above:
                    _swap_order(cur["_id"], cur["order"], above["_id"], above["order"])
                    toast("이동 완료!", icon="✅")
                    st.rerun()
        with o2:
            if st.button("🔽 아래로", use_container_width=True, key="job_move_down_btn"):
                cur = edit_row
                below = None
                for rr in rows:
                    if rr["order"] > cur["order"]:
                        below = rr
                        break
                if below:
                    _swap_order(cur["_id"], cur["order"], below["_id"], below["order"])
                    toast("이동 완료!", icon="✅")
                    st.rerun()

    st.divider()

    # -------------------------------------------------
    # ✅ 직업 CSV 일괄 업로드 (정원 컬럼 없음)
    # -------------------------------------------------
    st.markdown("### 📥 직업 CSV 일괄 업로드")
    st.caption("CSV 컬럼은 반드시: 순 | 직업 | 월급 이어야 합니다. (정원/사람수 없음)")

    import io
    sample_df = pd.DataFrame(
        [
            {"순": 1, "직업": "반장", "월급": 500},
            {"순": 2, "직업": "서기", "월급": 300},
        ]
    )
    bio = io.StringIO()
    sample_df.to_csv(bio, index=False, encoding="utf-8-sig")
    st.download_button(
        "📄 직업 샘플 CSV 다운로드",
        data=bio.getvalue().encode("utf-8-sig"),
        file_name="jobs_sample.csv",
        mime="text/csv",
        use_container_width=True,
        key="jobs_sample_csv_btn",
    )

    up = st.file_uploader("CSV 업로드", type=["csv"], key="jobs_bulk_up")
    col1, col2 = st.columns([1, 1])
    with col1:
        wipe = st.checkbox("업로드 전 기존 직업 목록 전체 삭제", value=False, key="jobs_bulk_wipe")
    with col2:
        if st.button("⬆️ 업로드 적용", use_container_width=True, key="jobs_bulk_apply", disabled=(up is None)):
            try:
                df = pd.read_csv(up)
                need_cols = {"순", "직업", "월급"}
                if not need_cols.issubset(set(df.columns)):
                    st.error("CSV 컬럼은 반드시: 순 | 직업 | 월급 이어야 합니다.")
                    st.stop()

                df["순"] = pd.to_numeric(df["순"], errors="coerce").fillna(0).astype(int)
                df["월급"] = pd.to_numeric(df["월급"], errors="coerce").fillna(0).astype(int)
                df["직업"] = df["직업"].astype(str).str.strip()

                df = df[(df["순"] > 0) & (df["월급"] >= 0) & (df["직업"] != "")]
                df = df.sort_values("순", kind="mergesort")

                if wipe:
                    # 전체 삭제
                    batch = db.batch()
                    for d in db.collection("job_salary").stream():
                        batch.delete(d.reference)
                    batch.commit()

                # 업로드(순서대로 새로 추가)
                for _, r in df.iterrows():
                    db.collection("job_salary").document().set(
                        {
                            "order": int(r["순"]),
                            "job": str(r["직업"]),
                            "salary": int(r["월급"]),
                            "student_count": 0,
                            "assigned_ids": [],
                            "created_at": firestore.SERVER_TIMESTAMP,
                        }
                    )

                toast("업로드 완료!", icon="✅")
                api_list_accounts_cached.clear()
                st.rerun()
            except Exception as e:
                st.error(f"업로드 실패: {e}")
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
        "ts": now,
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
    view = df_tx.rename(
        columns={
            "created_at_kr": "날짜-시간",
            "memo": "내역",
            "deposit": "입금",
            "withdraw": "출금",
            "balance_after": "총액",
        }
    )
    st.dataframe(
        view[["내역", "입금", "출금", "총액", "날짜-시간"]],
        use_container_width=True,
        hide_index=True,
    )


def render_active_savings_list(savings: list[dict], name: str, pin: str, balance_now: int):
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
            total_amt = principal + interest2
            st.write(
                f"- 원금 **{principal}**, 기간 **{weeks}주**, 만기일 **{mkr}**, 만기 이자 **{interest2}**, 만기시 총 금액 **{total_amt}**"
            )

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
    st.markdown("### 🎯 목표 저금")
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

    # ✅ 목표 계산:
    # - 진행중(active) 적금은 "자산"이므로 원금은 항상 포함
    # - 목표 날짜 이전 만기되는 적금만 이자까지 포함
    principal_all_active = 0
    interest_before_goal = 0

    for s in savings_list:
        if str(s.get("status", "")).lower().strip() != "active":
            continue

        principal = int(s.get("principal", 0) or 0)
        interest3 = int(s.get("interest", 0) or 0)
        principal_all_active += principal

        mdt = s.get("maturity_date")
        if isinstance(mdt, datetime):
            m_date = mdt.astimezone(KST).date()
            if m_date <= goal_date:
                interest_before_goal += interest3

    inv_now = _get_invest_summary_by_student_id(str(student_id or ""))[1]
    now_amount = current_balance + principal_all_active + int(inv_now)

    expected_amount = now_amount + interest_before_goal
    now_ratio = clamp01((now_amount / goal_amount) if goal_amount > 0 else 0)
    exp_ratio = clamp01((expected_amount / goal_amount) if goal_amount > 0 else 0)

    st.write(f"총 자산 기준: **{now_ratio*100:.1f}%** (현재 {current_balance} / 목표 {goal_amount})")
    st.progress(exp_ratio)
    st.write(f"총 자산 기준 예상 달성률: **{exp_ratio*100:.1f}%** (예상 {expected_amount} / 목표 {goal_amount})")

    if principal_all_active > 0:
        st.info(f"📌 진행 중 적금 원금 **+{principal_all_active}** 포함 (목표일 이후 만기 적금은 원금만 반영)")
    if interest_before_goal > 0:
        st.caption(f"※ 목표일({goal_date.isoformat()}) 이전 만기 적금 이자 **+{interest_before_goal}** 포함")
    if principal_all_active == 0 and interest_before_goal == 0:
        st.caption("진행 중 적금이 없어 예상 금액은 현재 잔액과 같아요.")

def render_goal_readonly_admin(student_id: str, balance_now: int, savings: list[dict]):
    """ ✅ (3번) 관리자 개별 탭: 목표 '조회'만 가능(수정/설정 UI 없음) """
    st.markdown("### 🎯 목표저금(조회)")
    gres = api_get_goal_by_student_id(student_id)
    if not gres.get("ok"):
        st.error(gres.get("error", "목표 정보를 불러오지 못했어요."))
        return

    goal_amount = int(gres.get("goal_amount", 0) or 0)
    goal_date_str = str(gres.get("goal_date", "") or "")

    if goal_amount <= 0:
        st.caption("설정된 목표가 없습니다.")
        return

    goal_date = None
    if goal_date_str:
        try:
            goal_date = datetime.fromisoformat(goal_date_str).date()
        except Exception:
            goal_date = None

    principal_all_active = 0
    interest_before_goal = 0

    if goal_date:
        for s in savings or []:
            if str(s.get("status", "")).lower().strip() != "active":
                continue

            principal = int(s.get("principal", 0) or 0)
            interest3 = int(s.get("interest", 0) or 0)
            principal_all_active += principal

            mdt = s.get("maturity_date")
            if isinstance(mdt, datetime):
                m_date = mdt.astimezone(KST).date()
                if m_date <= goal_date:
                    interest_before_goal += interest3

    expected_amount = int(balance_now) + int(principal_all_active) + int(interest_before_goal)
    exp_ratio = clamp01(expected_amount / goal_amount if goal_amount > 0 else 0)

    st.write(f"- 목표 금액: **{goal_amount}**")
    if goal_date:
        st.write(f"- 목표 날짜: **{goal_date.isoformat()}**")
    elif goal_date_str:
        st.write(f"- 목표 날짜: **{goal_date_str}**")

    st.progress(exp_ratio)
    st.write(
        f"예상 달성률(목표일 기준 총 자산): **{exp_ratio*100:.1f}%** "
        f"(예상 {expected_amount} / 목표 {goal_amount})"
    )

    if goal_date and (principal_all_active > 0 or interest_before_goal > 0):
        st.caption(
            f"※ 진행 중 적금 원금 +{principal_all_active} 포함 / "
            f"목표일({goal_date.isoformat()}) 이전 만기 이자 +{interest_before_goal} 포함"
        )


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
if st.session_state.get("logged_in", False):
    _who = str(st.session_state.get("login_name", "") or "").strip()
    st.subheader(f"🔐 로그인({_who})" if _who else "🔐 로그인")
else:
    st.subheader("🔐 로그인")

qp = st.query_params
saved_name = str(qp.get("saved_name", "") or "")

if not st.session_state.logged_in:
    # ✅ Enter로 로그인 제출 가능하도록 form 사용
    with st.form("login_form", clear_on_submit=False):
        login_c1, login_c2, login_c3 = st.columns([2, 2, 1])
        with login_c1:
            login_name = st.text_input("이름", value=saved_name, key="login_name_input").strip()
            remember = st.checkbox("이름 저장", value=bool(saved_name), key="remember_name")
        with login_c2:
            login_pin = st.text_input("비밀번호(4자리)", type="password", key="login_pin_input").strip()
        with login_c3:
            login_btn = st.form_submit_button("로그인", use_container_width=True)

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
        st.session_state.undo_mode = False
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


def template_display_for_trade(t):
    kind_kr = "입금" if t["kind"] == "deposit" else "출금"
    return f"{t['label']}[{kind_kr} {int(t['amount'])}]"


# ✅ [버그 수정 핵심] 표시 문자열(셀렉트박스 값) → 템플릿으로 바로 매핑
TEMPLATE_BY_DISPLAY = {template_display_for_trade(t): t for t in TEMPLATES}

# =========================
# ✅ 공용: 거래 입력 UI (설정탭 방식 그대로)
# - 원형 버튼 + 템플릿 반영 + 금액(+) / 금액(-) + 계산기 방식(net)
# =========================
def render_admin_trade_ui(prefix: str, templates_list: list, template_by_display: dict):
    """
    ✅ 공용: 거래 입력 UI
    - Streamlit에 st.fragment가 있으면 "빠른금액 UI"만 부분 rerun → 버튼 반응 즉시(설정탭처럼)
    - st.fragment가 없으면 기존 방식(전체 rerun)으로 동작
    """
    memo_key = f"{prefix}_memo"
    dep_key = f"{prefix}_dep"
    wd_key = f"{prefix}_wd"
    tpl_key = f"{prefix}_tpl"
    mode_key = f"{prefix}_mode"
    prev_key = f"{prefix}_quick_prev"

    out_key = f"{prefix}_trade_out"

    st.session_state.setdefault(memo_key, "")
    st.session_state.setdefault(dep_key, 0)
    st.session_state.setdefault(wd_key, 0)
    st.session_state.setdefault(tpl_key, "(직접 입력)")
    st.session_state.setdefault(mode_key, "금액(+)")
    st.session_state.setdefault(prev_key, None)

        # ✅ 저장 후 reset 요청이 들어오면, 위젯 생성 전에 초기화
    reset_flag_key = f"{prefix}_reset_request"
    if st.session_state.get(reset_flag_key, False):
        st.session_state[memo_key] = ""
        st.session_state[dep_key] = 0
        st.session_state[wd_key] = 0
        st.session_state[tpl_key] = "(직접 입력)"
        st.session_state[mode_key] = "금액(+)"
        st.session_state[prev_key] = None
        st.session_state[reset_flag_key] = False

    def _get_net() -> int:
        dep = int(st.session_state.get(dep_key, 0) or 0)
        wd = int(st.session_state.get(wd_key, 0) or 0)
        return dep - wd

    def _set_by_net(net: int):
        net = int(net or 0)
        if net >= 0:
            st.session_state[dep_key] = net
            st.session_state[wd_key] = 0
        else:
            st.session_state[dep_key] = 0
            st.session_state[wd_key] = -net

    def _apply_amt(amt: int):
        amt = int(amt or 0)
        if amt == 0:
            st.session_state[dep_key] = 0
            st.session_state[wd_key] = 0
            return

        sign = 1 if st.session_state[mode_key] == "금액(+)" else -1
        net = _get_net() + (sign * amt)
        _set_by_net(net)

    # -------------------------
    # st.fragment 사용 가능 여부
    # -------------------------
    _frag = getattr(st, "fragment", None)
    use_fragment = callable(_frag)

    # -------------------------
    # 실제 UI 그리는 부분 (fragment 안에서만 부분 rerun 되도록)
    # -------------------------
    def _draw_ui():
        # 템플릿 (선택이 바뀔 때만 1회 세팅)
        tpl_prev_key = f"{prefix}_tpl_prev"
        st.session_state.setdefault(tpl_prev_key, "(직접 입력)")

        tpl_labels = ["(직접 입력)"] + [template_display_for_trade(t) for t in templates_list]
        sel = st.selectbox("내역 템플릿", tpl_labels, key=tpl_key)

        if sel != st.session_state.get(tpl_prev_key):
            st.session_state[tpl_prev_key] = sel

                        # ✅ 템플릿 바꾸면 "빠른금액 원형버튼" 선택만 0으로 리셋 (금액칸은 유지)
            st.session_state[f"{prefix}_quick_pick"] = "0"
            st.session_state[f"{prefix}_quick_pick_prev"] = "0"
            st.session_state[f"{prefix}_quick_skip_once"] = True

            if sel != "(직접 입력)":
                tpl = template_by_display.get(sel)
                if tpl:
                    st.session_state[memo_key] = tpl["label"]
                    amt = int(tpl["amount"])

                    if tpl["kind"] == "deposit":
                        _set_by_net(amt)
                        st.session_state[mode_key] = "금액(+)"
                    else:
                        _set_by_net(-amt)
                        st.session_state[mode_key] = "금액(-)"

                    st.session_state[f"{prefix}_quick_skip_once"] = True

            # ✅ fragment 모드에서는 st.rerun() 금지 (전체 rerun 방지)
            if not use_fragment:
                st.rerun()

        st.text_input("내역", key=memo_key)

        # -------------------------
        # 빠른 금액(원형 버튼) + 모드(금액+/금액-)
        # -------------------------
        st.caption("⚡ 빠른 금액(원형 버튼)")
        QUICK_AMOUNTS = [0, 10, 20, 50, 100, 200, 500, 1000]

        pick_key = f"{prefix}_quick_pick"
        st.session_state.setdefault(pick_key, "0")

        skip_key = f"{prefix}_quick_skip_once"
        st.session_state.setdefault(skip_key, False)

        def _on_mode_change():
            st.session_state[pick_key] = "0"
            st.session_state[skip_key] = True
            st.session_state[f"{prefix}_quick_pick_prev"] = "0"
            st.session_state[f"{prefix}_quick_mode_prev"] = str(st.session_state.get(mode_key, "금액(+)"))

        st.radio(
            "적용",
            ["금액(+)", "금액(-)"],
            horizontal=True,
            key=mode_key,
            on_change=_on_mode_change,
        )

        st.markdown("<div class='round-btns'>", unsafe_allow_html=True)
        opts = [str(a) for a in QUICK_AMOUNTS]
        st.radio(
            "빠른금액",
            opts,
            horizontal=True,
            label_visibility="collapsed",
            key=pick_key,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        mode_prev_key = f"{prefix}_quick_mode_prev"
        pick_prev_key = f"{prefix}_quick_pick_prev"

        cur_mode = str(st.session_state.get(mode_key, "금액(+)"))
        cur_pick = str(st.session_state.get(pick_key, "0"))

        st.session_state.setdefault(mode_prev_key, cur_mode)
        st.session_state.setdefault(pick_prev_key, cur_pick)

        # ✅ 템플릿 자동세팅/모드변경 직후 1회는 반영 스킵
        if st.session_state.get(skip_key, False):
            st.session_state[mode_prev_key] = cur_mode
            st.session_state[pick_prev_key] = cur_pick
            st.session_state[skip_key] = False
        else:
            prev_mode = str(st.session_state.get(mode_prev_key, cur_mode))
            prev_pick = str(st.session_state.get(pick_prev_key, cur_pick))

            # 1) 모드만 바뀐 경우: 계산 금지(그냥 prev 갱신)
            if cur_mode != prev_mode:
                st.session_state[mode_prev_key] = cur_mode
                st.session_state[pick_prev_key] = cur_pick

            # 2) 숫자가 바뀐 경우: 이때만 계산
            elif cur_pick != prev_pick:
                st.session_state[pick_prev_key] = cur_pick
                _apply_amt(int(cur_pick))

                # ✅ fragment 모드에서는 st.rerun() 금지 (전체 rerun 방지)
                if not use_fragment:
                    st.rerun()

        c1, c2 = st.columns(2)
        with c1:
            st.number_input("입금", min_value=0, step=1, key=dep_key)
        with c2:
            st.number_input("출금", min_value=0, step=1, key=wd_key)

        memo = str(st.session_state.get(memo_key, "") or "").strip()
        dep = int(st.session_state.get(dep_key, 0) or 0)
        wd = int(st.session_state.get(wd_key, 0) or 0)
        st.session_state[out_key] = (memo, dep, wd)

    # ✅ fragment가 있으면 "이 UI 부분만" 부분 rerun
    if use_fragment:
        @_frag
        def _frag_draw():
            _draw_ui()

        _frag_draw()
    else:
        _draw_ui()

    # 밖에서는 session_state에서 값을 꺼내 반환(저장 버튼 눌렀을 때 최신값으로 잡힘)
    memo, dep, wd = st.session_state.get(out_key, ("", 0, 0))
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

    tab_labels = ["⚙️ 설정", "📒 전체통장", "💼 직업/월급", "📈 투자"] + [f"👤 {a['name']}" for a in filtered]
    tabs = st.tabs(tab_labels)

    admin_pin = ADMIN_PIN


    # -------------------------
    # ⚙️ 설정 탭
    # -------------------------
    with tabs[0]:
        st.subheader("⚙️ 설정")

        # -------------------------------------------------
        # 1) ✅ 전체 일괄 지급/벌금 (단일 UI로 통일)
        # -------------------------------------------------
        st.markdown("### 🎁 전체 일괄 지급/벌금")

        tpl_res3 = api_list_templates_cached()
        templates3 = tpl_res3.get("templates", []) if tpl_res3.get("ok") else []
        tpl_by_display3 = {template_display_for_trade(t): t for t in templates3}

        memo_bulk, dep_bulk, wd_bulk = render_admin_trade_ui(
            prefix="admin_bulk_onebox",
            templates_list=templates3,
            template_by_display=tpl_by_display3,
        )

        # ✅ 저장(1개) + 되돌리기(관리자) 로 통일
        b1, b2 = st.columns(2)

        with b1:
            if st.button("저장", key="bulk_save_setting", use_container_width=True):

                if (dep_bulk > 0 and wd_bulk > 0) or (dep_bulk == 0 and wd_bulk == 0):
                    st.error("입금/출금은 둘 중 하나만 입력해 주세요.")
                elif not memo_bulk:
                    st.error("내역(메모)을 입력해 주세요.")
                else:
                    # 입금/출금 자동 판별
                    if dep_bulk > 0:
                        res = api_admin_bulk_deposit(admin_pin, dep_bulk, memo_bulk)
                        if res.get("ok"):
                            toast(f"일괄 지급 완료! ({res.get('count')}명)", icon="🎉")
                            api_list_accounts_cached.clear()
                            st.rerun()
                        else:
                            st.error(res.get("error", "일괄 지급 실패"))
                    else:
                        res = api_admin_bulk_withdraw(admin_pin, wd_bulk, memo_bulk)
                        if res.get("ok"):
                            toast(f"벌금 완료! (적용 {res.get('count')}명)", icon="⚠️")
                            api_list_accounts_cached.clear()
                            st.rerun()
                        else:
                            st.error(res.get("error", "일괄 벌금 실패"))

        with b2:
            if st.button("되돌리기(관리자)", key="bulk_undo_toggle_setting", use_container_width=True):
                st.session_state["bulk_undo_mode"] = not st.session_state.get("bulk_undo_mode", False)

        # -------------------------
        # ✅ 설정탭 되돌리기(관리자)
        # -------------------------
        if st.session_state.get("bulk_undo_mode", False):
            st.divider()
            st.subheader("↩️ 선택 되돌리기(관리자)")

            admin_pin_rb = st.text_input(
                "관리자 PIN 입력",
                type="password",
                key="bulk_undo_admin_pin_setting",
            ).strip()

            accounts_for_rb = api_list_accounts_cached().get("accounts", [])
            name_map = {a["name"]: a["student_id"] for a in accounts_for_rb}

            pick_name = st.selectbox(
                "되돌릴 학생 선택",
                ["(선택)"] + list(name_map.keys()),
                key="bulk_undo_pick_name_setting",
            )

            if pick_name != "(선택)":
                sid_rb = name_map.get(pick_name, "")
                txr_rb = api_get_txs_by_student_id(sid_rb, limit=120)
                df_rb = pd.DataFrame(txr_rb.get("rows", [])) if txr_rb.get("ok") else pd.DataFrame()

                if not df_rb.empty:
                    view_df = df_rb.head(50).copy()

                    def _can_rollback_row(row):
                        if str(row.get("type", "")) == "rollback":
                            return False
                        if _is_savings_memo(row.get("memo", "")) or str(row.get("type", "")) in ("maturity",):
                            return False
                        return True

                    view_df["가능"] = view_df.apply(_can_rollback_row, axis=1)

                    selected_ids = []
                    for _, r in view_df.iterrows():
                        tx_id = r["tx_id"]
                        label = f"{r['created_at_kr']} | {r['memo']} | +{int(r['deposit'])} / -{int(r['withdraw'])}"
                        ck = st.checkbox(label, key=f"bulk_rb_ck_{sid_rb}_{tx_id}", disabled=(not r["가능"]))
                        if ck and r["가능"]:
                            selected_ids.append(tx_id)

                    if st.button("선택 항목 되돌리기", key="bulk_do_rb_setting", use_container_width=True):
                        if not is_admin_pin(admin_pin_rb):
                            st.error("관리자 PIN이 틀립니다.")
                        elif not selected_ids:
                            st.warning("체크된 항목이 없어요.")
                        else:
                            res2 = api_admin_rollback_selected(admin_pin_rb, sid_rb, selected_ids)
                            if res2.get("ok"):
                                toast(f"선택 {res2.get('undone')}건 되돌림 완료", icon="↩️")
                                api_list_accounts_cached.clear()
                                st.rerun()
                            else:
                                st.error(res2.get("error", "되돌리기 실패"))

        st.divider()

        # -------------------------------------------------
        # 2) ✅ (1번) 템플릿 정렬/관리 = "접기/펼치기" (기본 접힘)
        # -------------------------------------------------
        h1, h2 = st.columns([0.35, 9.65], vertical_alignment="center")
        with h1:
            if st.button(
                "▸" if not st.session_state.tpl_sort_panel_open else "▾",
                key="tpl_sort_panel_toggle",
                use_container_width=True,
            ):
                st.session_state.tpl_sort_panel_open = not st.session_state.tpl_sort_panel_open
                st.rerun()
        with h2:
            st.markdown("### 🧩 내역 템플릿 순서 정렬")

        if not st.session_state.tpl_sort_panel_open:
            st.caption("펼치려면 왼쪽 화살표(▸)를 눌러주세요.")
        else:
            tpl_res2 = api_list_templates_cached()
            templates = tpl_res2.get("templates", []) if tpl_res2.get("ok") else []
            templates = sorted(
                templates,
                key=lambda t: (int(t.get("order", 999999) or 999999), str(t.get("label", ""))),
            )
            tpl_by_id = {t["template_id"]: t for t in templates}

            if not st.session_state.tpl_sort_mode:
                st.session_state.tpl_work_ids = [t["template_id"] for t in templates]
            else:
                cur_ids = [t["template_id"] for t in templates]
                if (not st.session_state.tpl_work_ids) or (set(st.session_state.tpl_work_ids) != set(cur_ids)):
                    st.session_state.tpl_work_ids = cur_ids

            topA, topB, topC, topD = st.columns([1.1, 1.1, 1.4, 1.6])
            with topA:
                if st.button(
                    "정렬모드 ON" if not st.session_state.tpl_sort_mode else "정렬모드 OFF",
                    key="tpl_sort_toggle",
                    use_container_width=True,
                ):
                    st.session_state.tpl_sort_mode = not st.session_state.tpl_sort_mode
                    if not st.session_state.tpl_sort_mode:
                        st.session_state.tpl_work_ids = [t["template_id"] for t in templates]
                    st.rerun()
            with topB:
                if st.button("order 채우기(1회)", key="tpl_backfill_btn2", use_container_width=True):
                    res = api_admin_backfill_template_order(admin_pin)
                    if res.get("ok"):
                        toast("order 초기화 완료!", icon="🧷")
                        api_list_templates_cached.clear()
                        st.session_state.tpl_work_ids = []
                        st.rerun()
                    else:
                        st.error(res.get("error", "실패"))
            with topC:
                if st.button("order 전체 재정렬", key="tpl_normalize_btn2", use_container_width=True):
                    res = api_admin_normalize_template_order(admin_pin)
                    if res.get("ok"):
                        toast("order 재정렬 완료!", icon="🧹")
                        api_list_templates_cached.clear()
                        st.session_state.tpl_work_ids = []
                        st.rerun()
                    else:
                        st.error(res.get("error", "실패"))
            with topD:
                st.session_state.tpl_mobile_sort_ui = st.checkbox(
                    "간단 모드(모바일용)",
                    value=bool(st.session_state.tpl_mobile_sort_ui),
                    key="tpl_mobile_sort_ui_chk",
                    help="모바일에서 표가 세로로 쌓여 보이는 문제를 피하기 위한 정렬 UI입니다.",
                )

            if st.session_state.tpl_sort_mode:
                st.caption("✅ 이동은 화면에서만 즉시 반영 → 마지막에 ‘저장(한 번에)’ 1번 누르면 DB 반영")

            work_ids = st.session_state.tpl_work_ids
            if not work_ids:
                st.info("템플릿이 아직 없어요.")
            else:
                if st.session_state.tpl_mobile_sort_ui:
                    options = list(range(len(work_ids)))

                    def _opt_label(i: int):
                        tid = work_ids[i]
                        t = tpl_by_id.get(tid, {})
                        kind_kr = "입금" if t.get("kind") == "deposit" else "출금"
                        amt = int(t.get("amount", 0) or 0)
                        return f"{i+1}. {t.get('label','')} ({kind_kr} {amt})"

                    pick_i = st.selectbox(
                        "이동할 항목 선택",
                        options,
                        format_func=_opt_label,
                        key="tpl_simple_pick",
                    )

                    b1, b2, b3 = st.columns([1, 1, 2])
                    with b1:
                        if st.button(
                            "위로 ▲",
                            key="tpl_simple_up",
                            disabled=(not st.session_state.tpl_sort_mode) or pick_i == 0,
                            use_container_width=True,
                        ):
                            work_ids[pick_i - 1], work_ids[pick_i] = work_ids[pick_i], work_ids[pick_i - 1]
                            st.session_state.tpl_work_ids = work_ids
                            st.session_state["tpl_simple_pick"] = max(0, pick_i - 1)
                            st.rerun()
                    with b2:
                        if st.button(
                            "아래로 ▼",
                            key="tpl_simple_dn",
                            disabled=(not st.session_state.tpl_sort_mode) or pick_i == (len(work_ids) - 1),
                            use_container_width=True,
                        ):
                            work_ids[pick_i + 1], work_ids[pick_i] = work_ids[pick_i], work_ids[pick_i + 1]
                            st.session_state.tpl_work_ids = work_ids
                            st.session_state["tpl_simple_pick"] = min(len(work_ids) - 1, pick_i + 1)
                            st.rerun()
                    with b3:
                        st.caption("정렬모드 ON일 때만 이동 가능")

                    html = ["<div class='tpl-simple'>"]
                    for idx, tid in enumerate(work_ids, start=1):
                        t = tpl_by_id.get(tid, {})
                        kind_kr = "입금" if t.get("kind") == "deposit" else "출금"
                        amt = int(t.get("amount", 0) or 0)
                        lab = str(t.get("label", "") or "")
                        html.append(
                            f"<div class='item'>"
                            f"<span class='idx'>{idx}</span>"
                            f"<span class='lab'>{lab}</span>"
                            f"<div class='meta'>{kind_kr} · {amt}</div>"
                            f"</div>"
                        )
                    html.append("</div>")
                    st.markdown("\n".join(html), unsafe_allow_html=True)

                    if st.session_state.tpl_sort_mode:
                        s1, s2 = st.columns([1.2, 1.2])
                        with s1:
                            if st.button("저장(한 번에)", key="tpl_save_orders_btn_simple", use_container_width=True):
                                res = api_admin_save_template_orders(admin_pin, st.session_state.tpl_work_ids)
                                if res.get("ok"):
                                    toast(f"순서 저장 완료! ({res.get('count', 0)}개)", icon="💾")
                                    st.session_state.tpl_sort_mode = False
                                    api_list_templates_cached.clear()
                                    st.session_state.tpl_work_ids = []
                                    st.rerun()
                                else:
                                    st.error(res.get("error", "저장 실패"))
                        with s2:
                            if st.button("취소(원복)", key="tpl_cancel_orders_btn_simple", use_container_width=True):
                                st.session_state.tpl_sort_mode = False
                                st.session_state.tpl_work_ids = [t["template_id"] for t in templates]
                                toast("변경 취소(원복)!", icon="↩️")
                                st.rerun()

                else:
                    head = st.columns([0.7, 5.2, 2.2, 1.4], vertical_alignment="center")
                    head[0].markdown("<div class='tpl-head'>순서</div>", unsafe_allow_html=True)
                    head[1].markdown("<div class='tpl-head'>내역</div>", unsafe_allow_html=True)
                    head[2].markdown("<div class='tpl-head'>종류·금액</div>", unsafe_allow_html=True)
                    head[3].markdown("<div class='tpl-head'>이동</div>", unsafe_allow_html=True)

                    for idx, tid in enumerate(work_ids):
                        t = tpl_by_id.get(tid, {})
                        label = t.get("label", "")
                        kind_kr = "입금" if t.get("kind") == "deposit" else "출금"
                        amt = int(t.get("amount", 0) or 0)

                        row = st.columns([0.7, 5.2, 2.2, 0.7, 0.7], vertical_alignment="center")
                        row[0].markdown(f"<div class='tpl-cell'>{idx+1}</div>", unsafe_allow_html=True)
                        row[1].markdown(
                            f"<div class='tpl-cell'><div class='tpl-label'>{label}</div></div>",
                            unsafe_allow_html=True,
                        )
                        row[2].markdown(
                            f"<div class='tpl-cell'><div class='tpl-sub'>{kind_kr} · {amt}</div></div>",
                            unsafe_allow_html=True,
                        )

                        if st.session_state.tpl_sort_mode:
                            up_disabled = (idx == 0)
                            down_disabled = (idx == len(work_ids) - 1)

                            if row[3].button("⬆", key=f"tpl_up_fast_{tid}", disabled=up_disabled, use_container_width=True):
                                work_ids[idx - 1], work_ids[idx] = work_ids[idx], work_ids[idx - 1]
                                st.session_state.tpl_work_ids = work_ids
                                st.rerun()

                            if row[4].button("⬇", key=f"tpl_dn_fast_{tid}", disabled=down_disabled, use_container_width=True):
                                work_ids[idx + 1], work_ids[idx] = work_ids[idx], work_ids[idx + 1]
                                st.session_state.tpl_work_ids = work_ids
                                st.rerun()
                        else:
                            row[3].markdown("<div class='tpl-cell'></div>", unsafe_allow_html=True)
                            row[4].markdown("<div class='tpl-cell'></div>", unsafe_allow_html=True)

                    if st.session_state.tpl_sort_mode:
                        s1, s2 = st.columns([1.2, 1.2])
                        with s1:
                            if st.button("저장(한 번에)", key="tpl_save_orders_btn", use_container_width=True):
                                res = api_admin_save_template_orders(admin_pin, st.session_state.tpl_work_ids)
                                if res.get("ok"):
                                    toast(f"순서 저장 완료! ({res.get('count', 0)}개)", icon="💾")
                                    st.session_state.tpl_sort_mode = False
                                    api_list_templates_cached.clear()
                                    st.session_state.tpl_work_ids = []
                                    st.rerun()
                                else:
                                    st.error(res.get("error", "저장 실패"))
                        with s2:
                            if st.button("취소(원복)", key="tpl_cancel_orders_btn", use_container_width=True):
                                st.session_state.tpl_sort_mode = False
                                st.session_state.tpl_work_ids = [t["template_id"] for t in templates]
                                toast("변경 취소(원복)!", icon="↩️")
                                st.rerun()

        st.divider()

        # -------------------------------------------------
        # 3) 템플릿 추가/수정/삭제
        # -------------------------------------------------
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
            kind_kr = "입금" if t["kind"] == "deposit" else "출금"
            return f"{t['label']}[{kind_kr} {int(t['amount'])}]"

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
                key="tpl_pick_setting2",
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
                key="tpl_del_pick_setting2",
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

        # -------------------------------------------------
        # 4) PIN 재설정 (맨 아래)
        # -------------------------------------------------
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
    # 📒 전체통장(사람별 통장 내역)
    # -------------------------
    with tabs[1]:
        st.subheader("📒 전체통장 내역")
        for a in filtered:
            nm, sid = a["name"], a["student_id"]
            sres = api_savings_list_by_student_id(sid)
            savings = sres.get("savings", []) if sres.get("ok") else []
            sv_total = savings_active_total(savings)
            bal_now = int(a.get("balance", 0) or 0)
            asset_total = bal_now + sv_total

            with st.expander(f"👤 {nm} | 총액 {asset_total} · 통장 {bal_now} · 적금 {sv_total}", expanded=False):
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
    # 💼 직업/월급 (관리자)
    # -------------------------
    with tabs[2]:
        _render_jobs_admin_like()

    # -------------------------
    # 📈 투자 (관리자)
    # -------------------------
    with tabs[3]:
        _render_invest_admin_like(
            inv_admin_ok_flag=True,
            force_is_admin=True,
            my_student_id=None,
            login_name=st.session_state.login_name,
            login_pin=st.session_state.login_pin,
        )

    # -------------------------
    # 👤 각 사용자별 탭
    # -------------------------
    for i, a in enumerate(filtered, start=4):
        with tabs[i]:
            nm, sid = a["name"], a["student_id"]

            # ✅ (class앱 기준) 직업/투자 현재평가 표시
            _role = _get_role_name_by_student_id(str(sid))
            _inv_text, _inv_total = _get_invest_summary_by_student_id(str(sid))
            st.caption(f"직업: {_role} · 투자(현재평가): {int(_inv_total)} 포인트")

            txr = api_get_txs_by_student_id(sid, limit=300)
            df_tx = pd.DataFrame(txr.get("rows", [])) if txr.get("ok") else pd.DataFrame()

            sres = api_savings_list_by_student_id(sid)
            savings = sres.get("savings", []) if sres.get("ok") else []

            bal_now = int(a.get("balance", 0) or 0)

            st.subheader(f"👤 {nm}")
            render_asset_summary(bal_now, savings)

            st.markdown("### 📒 통장내역")
            if not df_tx.empty:
                df_tx = df_tx.sort_values("created_at_utc", ascending=False)
                render_tx_table(df_tx)

            # ✅ 개별 관리자 입금/출금 (캡쳐와 동일 형식으로 통일)
            st.divider()
            st.markdown("### 🧾 개별 관리자 입금/출금")

            memo_ind, dep_ind, wd_ind = render_admin_trade_ui(
                prefix=f"admin_ind_onebox_{sid}",
                templates_list=TEMPLATES,
                template_by_display=TEMPLATE_BY_DISPLAY,
            )

            st.caption("※ 관리자의 출금(벌금)은 잔액 부족이어도 적용되어 통장 잔액이 음수가 될 수 있어요.")

            if st.button("저장(관리자)", key=f"admin_ind_save_{sid}", use_container_width=True):
                if not memo_ind:
                    st.error("내역(메모)을 입력해 주세요.")
                elif (dep_ind > 0 and wd_ind > 0) or (dep_ind == 0 and wd_ind == 0):
                    st.error("입금/출금은 둘 중 하나만 입력해 주세요.")
                else:
                    res = api_admin_add_tx_by_student_id(ADMIN_PIN, sid, memo_ind, dep_ind, wd_ind)
                    if res.get("ok"):
                        toast("저장 완료!", icon="✅")
                        api_list_accounts_cached.clear()
                        st.rerun()
                    else:
                        st.error(res.get("error", "저장 실패"))

            # 적금 목록(조회)
            st.divider()
            render_active_savings_list(savings, name=f"admin_view_{nm}", pin="0000", balance_now=bal_now)

            # 목표저금 조회
            st.divider()
            render_goal_readonly_admin(student_id=sid, balance_now=bal_now, savings=savings)

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

df_tx = slot["df_tx"]
balance = int(slot["balance"])
student_id = slot.get("student_id")
savings_list = slot.get("savings", []) or []

sv_total = sum(
    int(s.get("principal", 0) or 0)
    for s in savings_list
    if str(s.get("status", "")).lower() == "active"
)

# ✅ (class앱 기준) 투자 현재 평가금(현재가치) + 직업명
inv_text, inv_total = _get_invest_summary_by_student_id(str(student_id or ""))
role_name = _get_role_name_by_student_id(str(student_id or ""))

asset_total = balance + sv_total + int(inv_total)

st.markdown(f"## 🧾 {name} 통장")
st.markdown(f"### 총 자산: **{asset_total} 포인트**")
st.markdown(f"#### 통장 잔액: **{balance} 포인트**")
st.markdown(f"#### 적금 금액: **{sv_total} 포인트**")
st.markdown(f"#### 투자 금액(현재 평가금): **{int(inv_total)} 포인트**")
st.markdown(f"#### 직업: **{role_name}**")

sub1, sub2, sub_invest, sub_job, sub3 = st.tabs(["📝 거래", "💰 적금", "📈 투자", "💼 직업", "🎯 목표"])

# =========================
# 거래 탭
# =========================
with sub1:
    st.subheader("📝 거래 기록(통장에 찍기)")

    # ✅ 사용자도 관리자 설정탭 입력 UI를 그대로 사용 (완전 동일 동작)
    memo_u, dep_u, wd_u = render_admin_trade_ui(
        prefix=f"user_trade_{name}",
        templates_list=TEMPLATES,
        template_by_display=TEMPLATE_BY_DISPLAY,
    )

    col_btn1, col_btn2 = st.columns([1, 1])

    with col_btn1:
        if st.button("저장", key=f"save_{name}", use_container_width=True):
            memo = str(memo_u or "").strip()
            deposit = int(dep_u or 0)
            withdraw = int(wd_u or 0)

            if not memo:
                st.error("내역을 입력해 주세요.")
            elif (deposit > 0 and withdraw > 0) or (deposit == 0 and withdraw == 0):
                st.error("입금/출금은 둘 중 하나만 입력해 주세요.")
            else:
                # ✅ 일반 사용자 출금은 잔액 부족이면 api_add_tx에서 막힘
                res = api_add_tx(name, pin, memo, deposit, withdraw)
                if res.get("ok"):
                    toast("저장 완료!", icon="✅")

                    # ✅ 속도 핵심: 전체 refresh_account_data(force=True) 제거
                    # 1) 잔액만 즉시 반영
                    new_bal = int(res.get("balance", balance) or balance)
                    st.session_state.data.setdefault(name, {})
                    st.session_state.data[name]["balance"] = new_bal

                    # 2) 거래내역은 '가볍게' 120개만 다시 불러오기(빠름)
                    if student_id:
                        tx_res = api_get_txs_by_student_id(student_id, limit=120)
                        if tx_res.get("ok"):
                            df_new = pd.DataFrame(tx_res.get("rows", []))
                            if not df_new.empty:
                                df_new = df_new.sort_values("created_at_utc", ascending=False)
                            st.session_state.data[name]["df_tx"] = df_new

                    pfx = f"user_trade_{name}"
                    st.session_state[f"{pfx}_reset_request"] = True

                    st.rerun()
                else:
                    st.error(res.get("error", "저장 실패"))

    with col_btn2:
        if st.button("되돌리기(관리자)", key=f"undo_btn_{name}", use_container_width=True):
            st.session_state.undo_mode = not st.session_state.undo_mode

    # -------------------------
    # 되돌리기(관리자 전용) - 기존 로직 유지
    # -------------------------
    if st.session_state.undo_mode:
        st.divider()
        st.subheader("↩️ 선택 되돌리기(관리자 전용)")

        admin_pin2 = st.text_input("관리자 PIN 입력", type="password", key=f"undo_admin_pin_{name}").strip()

        if df_tx is None or df_tx.empty:
            st.info("거래 내역이 없어요.")
        else:
            view_df = df_tx.head(50).copy()

            def _can_rollback_row(row):
                if str(row.get("type", "")) == "rollback":
                    return False
                if _is_savings_memo(row.get("memo", "")) or str(row.get("type", "")) in ("maturity",):
                    return False
                return True

            view_df["가능"] = view_df.apply(_can_rollback_row, axis=1)
            st.caption("✅ 체크한 항목만 되돌립니다. (적금/이미 되돌림/rollback은 제외)")

            selected_ids = []
            for _, r in view_df.iterrows():
                tx_id = r["tx_id"]
                memo2 = r["memo"]
                dtkr = r["created_at_kr"]
                dep2 = int(r["deposit"])
                wd2 = int(r["withdraw"])
                can = bool(r["가능"])
                label = f"{dtkr} | {memo2} | +{dep2} / -{wd2}"
                ck = st.checkbox(label, key=f"rb_ck_{name}_{tx_id}", disabled=(not can))
                if ck and can:
                    selected_ids.append(tx_id)

            cX, cY = st.columns([1, 2])
            with cX:
                if st.button("선택 항목 되돌리기", key=f"do_rb_{name}", use_container_width=True):
                    if not is_admin_pin(admin_pin2):
                        st.error("관리자 PIN이 틀립니다.")
                    elif not selected_ids:
                        st.warning("체크된 항목이 없어요.")
                    else:
                        res2 = api_admin_rollback_selected(admin_pin2, student_id, selected_ids)
                        if res2.get("ok"):
                            toast(f"선택 {res2.get('undone')}건 되돌림 완료", icon="↩️")
                            if res2.get("message"):
                                st.info(res2["message"])

                            # ✅ 되돌리기 후에는 거래내역이 중요하니 120개만 가볍게 갱신
                            tx_res2 = api_get_txs_by_student_id(student_id, limit=120)
                            if tx_res2.get("ok"):
                                df_new2 = pd.DataFrame(tx_res2.get("rows", []))
                                if not df_new2.empty:
                                    df_new2 = df_new2.sort_values("created_at_utc", ascending=False)
                                st.session_state.data[name]["df_tx"] = df_new2

                            # 잔액도 같이 갱신(가볍게 balance만 다시 읽기)
                            bal_res2 = api_get_balance(name, pin)
                            if bal_res2.get("ok"):
                                st.session_state.data[name]["balance"] = int(bal_res2.get("balance", 0) or 0)

                            st.session_state.undo_mode = False
                            st.rerun()
                        else:
                            st.error(res2.get("error", "되돌리기 실패"))
            with cY:
                st.caption("※ ‘적금 가입/해지/만기’는 되돌리기에서 제외됩니다.")

# =========================
# 적금 탭
# =========================
with sub2:
    st.subheader("💰 적금")

    p = st.number_input("적금 원금(10단위)", min_value=10, step=10, value=100, key=f"sv_p_{name}")
    w = st.selectbox("기간(1~10주)", list(range(1, 11)), index=4, key=f"sv_w_{name}")

    r, interest, maturity_amt, maturity_date = compute_preview(int(p), int(w))
    st.info(
        f"✅ 미리보기\n\n"
        f"- 이자율: **{int(r*100)}%**\n"
        f"- 만기일: **{maturity_date.strftime('%Y-%m-%d')}**\n"
        f"- 만기 수령액: **{maturity_amt} 포인트** (원금 {p} + 이자 {interest})"
    )

    if p > balance:
        st.warning("⚠️ 현재 잔액보다 원금이 커서 가입할 수 없어요.")

    if st.button("적금 가입", key=f"sv_join_{name}", disabled=(p > balance), use_container_width=True):
        res = api_savings_create(name, pin, int(p), int(w))
        if res.get("ok"):
            toast("적금 가입 완료!", icon="💰")
            refresh_account_data(name, pin, force=True)
            st.rerun()
        else:
            st.error(res.get("error", "적금 가입 실패"))

    st.divider()
    savings = st.session_state.data.get(name, {}).get("savings", [])
    render_active_savings_list(savings, name, pin, balance)


# =========================
# 투자 탭
# =========================
with sub_invest:
    st.subheader("📈 투자")
    _render_invest_admin_like(
        inv_admin_ok_flag=False,
        force_is_admin=False,
        my_student_id=str(student_id or ""),
        login_name=name,
        login_pin=pin,
    )

# =========================
# 직업 탭
# =========================
with sub_job:
    st.subheader("💼 직업")
    st.write(f"현재 직업: **{role_name}**")


# =========================
# 목표 탭
# =========================
with sub3:
    render_goal_section(name, pin, balance, savings_list)

# =========================
# 통장 내역(최신순)
# =========================
st.subheader("📒 통장 내역 (최신순)")
render_tx_table(df_tx)
