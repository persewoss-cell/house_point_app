// 🏷️ 경매 (기존 우리집 앱 데이터 그대로)
// config/auction_state · auction_rounds · auction_bids({회차id}_{가족id}) · auction_ledgers
// 입찰하면 바로 통장에서 빠지고, 장부 반영 때 '낙찰금 반환'을 고르면 떨어진 사람에게 90% 돌려줌(수수료 10%)
import { find, getOne, add, set, update, ref, tx, where, orderBy, qlimit, serverTimestamp } from "../db.js";
import { fail, requireLogin, requireAdmin, requireStudent, ADMIN_NAME } from "../auth.js";
import { str, toInt, toDate, fmtAuctionDt } from "../../shared/format.js";

const STATE = ["config", "auction_state"];
const pad2 = (n) => String(n).padStart(2, "0");

async function getState() {
  const d = await getOne(...STATE);
  if (!d || !d.active) return null;
  return { round_id: str(d.round_id), round_no: toInt(d.round_no), bid_title: str(d.bid_title), opened_at: d.opened_at };
}

async function recentRounds(n = 50) {
  return await find("auction_rounds", orderBy("round_no", "desc"), qlimit(n));
}

async function bidRows(roundId) {
  const docs = await find("auction_bids", where("round_id", "==", str(roundId)));
  return docs
    .map((x) => ({ amount: toInt(x.amount), t: toDate(x.submitted_at), name: str(x.student_name), sid: str(x.student_id) }))
    .sort((a, b) => b.amount - a.amount || (a.t ? a.t.getTime() : Infinity) - (b.t ? b.t.getTime() : Infinity));
}
const bidView = (rows) => rows.map((r) => ({ "입찰 가격": r.amount, 입찰일시: r.t ? fmtAuctionDt(r.t) : "", 이름: r.name }));

export default {
  async auction_admin_load(ctx, { pick_round_id }) {
    requireAdmin(ctx);
    const [open, rounds, ledgerDocs] = await Promise.all([getState(), recentRounds(50), find("auction_ledgers", orderBy("round_no", "desc"), qlimit(100))]);
    const closed = rounds
      .filter((r) => str(r.status) === "closed")
      .map((r) => ({ round_id: String(r._id), round_no: toInt(r.round_no), bid_title: str(r.bid_title), ledger_reflected: r.ledger_reflected === true }));
    let latest = null;
    if (closed[0]) latest = { ...closed[0], bids: bidView(await bidRows(closed[0].round_id)) };
    const picked_bids = pick_round_id ? bidView(await bidRows(pick_round_id)) : [];
    const ledger = ledgerDocs.map((x) => ({
      입찰번호: toInt(x.round_no),
      입찰기일: fmtAuctionDt(x.bid_date),
      입찰내역: str(x.bid_title),
      "입찰 참가수": toInt(x.participants),
      "총 액수": toInt(x.total_amount),
      "낙찰금 반환": x.refund_non_winner ? "적용" : "미적용",
      "반환 인원": toInt(x.refunded_count),
      "반환 금액": toInt(x.refunded_total),
      "차감 수수료": toInt(x.refunded_fee_total),
    }));
    return { open, closed, latest, picked_bids, ledger };
  },

  async auction_open(ctx, { bid_title }) {
    requireAdmin(ctx);
    const title = str(bid_title).trim();
    if (!title) fail("입찰 내역을 입력해 주세요.");
    if (await getState()) fail("이미 진행 중인 경매가 있습니다.");
    const top = (await recentRounds(1))[0];
    const round_no = toInt(top && top.round_no) + 1;
    const now = new Date();
    const id = await add("auction_rounds", { round_no, bid_title: title, status: "open", opened_at: now, closed_at: null, ledger_reflected: false });
    await set(...STATE, { active: true, round_id: id, round_no, bid_title: title, opened_at: now });
    return { round_no };
  },

  async auction_close(ctx) {
    requireAdmin(ctx);
    const s = await getState();
    if (!s) fail("진행 중인 경매가 없습니다.");
    await update("auction_rounds", s.round_id, { status: "closed", closed_at: serverTimestamp() });
    await set(...STATE, { active: false, round_id: null, round_no: null, bid_title: "", opened_at: null });
    return {};
  },

  // 장부 반영 (refund=true면 1등 빼고 입찰금의 90% 반환)
  async auction_apply(ctx, { round_id, refund }) {
    requireAdmin(ctx);
    const rd = await getOne("auction_rounds", round_id);
    if (!rd) fail("경매 회차를 찾을 수 없습니다.");
    if (rd.ledger_reflected === true) fail("이미 장부에 반영된 경매입니다.");
    // 두 번 반영되지 않도록 먼저 표시
    const rRef = ref("auction_rounds", round_id);
    const claimed = await tx(async (t) => {
      const s = await t.get(rRef);
      if (!s.exists() || s.data().ledger_reflected === true) return false;
      t.update(rRef, { ledger_reflected: true, ledger_reflected_at: serverTimestamp() });
      return true;
    });
    if (!claimed) fail("이미 장부에 반영된 경매입니다.");
    const bids = await bidRows(round_id);
    let total = bids.reduce((a, b) => a + b.amount, 0);
    const doRefund = !!refund && bids.length > 0;
    let refunded_count = 0;
    let refunded_total = 0;
    let refunded_fee_total = 0;
    if (doRefund) {
      const memo = `경매 입찰금 반환 ${pad2(toInt(rd.round_no))}회차 (수수료 10% 차감)`;
      for (const l of bids.slice(1)) {
        if (!l.sid || l.amount <= 0) continue;
        const fee = Math.floor(l.amount * 0.1 + 0.5); // 반올림(ROUND_HALF_UP)
        const back = Math.max(0, l.amount - fee);
        if (back <= 0) continue;
        const sRef = ref("students", l.sid);
        const tRef = ref("transactions");
        const ok = await tx(async (t) => {
          const s = await t.get(sRef);
          if (!s.exists()) return false;
          const nb = toInt(s.data().balance) + back;
          t.update(sRef, { balance: nb });
          t.set(tRef, { student_id: l.sid, type: "auction_bid_refund", amount: back, balance_after: nb, memo, recorded_by_name: ADMIN_NAME, created_at: serverTimestamp() });
          return true;
        });
        if (!ok) continue;
        refunded_count += 1;
        refunded_total += back;
        refunded_fee_total += fee;
      }
      total = bids[0].amount;
    }
    await add("auction_ledgers", {
      round_id: str(round_id),
      round_no: toInt(rd.round_no),
      bid_title: str(rd.bid_title),
      bid_date: rd.opened_at || null,
      participants: bids.length,
      total_amount: total,
      refund_non_winner: doRefund,
      refunded_count,
      refunded_total,
      refunded_fee_total,
      created_at: serverTimestamp(),
    });
    return { refunded_count, refunded_total };
  },

  async auction_user_load(ctx) {
    requireLogin(ctx);
    const open = await getState();
    let prev = null;
    if (open && ctx.sid) {
      const b = await getOne("auction_bids", `${open.round_id}_${ctx.sid}`);
      if (b) prev = { amount: toInt(b.amount), submitted_text: fmtAuctionDt(b.submitted_at) };
    }
    return { open: open ? { ...open, opened_text: fmtAuctionDt(open.opened_at) } : null, prev, me: { name: ctx.name } };
  },

  // 입찰표 제출 (한 회차에 한 번, 바로 통장에서 차감)
  async auction_bid(ctx, { amount }) {
    requireStudent(ctx);
    amount = toInt(amount);
    if (amount <= 0) fail("입찰 가격은 1 이상이어야 합니다.");
    const s0 = await getState();
    if (!s0) fail("진행 중인 경매가 없습니다.");
    const stRef = ref(...STATE);
    const bRef = ref("auction_bids", `${s0.round_id}_${ctx.sid}`);
    const sRef = ref("students", ctx.sid);
    const tRef = ref("transactions");
    await tx(async (t) => {
      const st = await t.get(stRef);
      const sd = st.exists() ? st.data() : {};
      if (!sd.active || str(sd.round_id) !== s0.round_id) fail("경매가 이미 마감되었거나 변경되었습니다.");
      if ((await t.get(bRef)).exists()) fail("이미 제출한 입찰표가 있습니다.");
      const me = await t.get(sRef);
      const bal = toInt(me.data().balance);
      if (bal < amount) fail("통장 잔액이 부족합니다.");
      const nb = bal - amount;
      t.update(sRef, { balance: nb });
      t.set(tRef, { student_id: ctx.sid, type: "auction_bid", amount: -amount, balance_after: nb, memo: `경매 입찰 ${pad2(s0.round_no)}회차`, recorded_by_name: ctx.name, created_at: serverTimestamp() });
      t.set(bRef, { round_id: s0.round_id, round_no: s0.round_no, student_id: ctx.sid, student_name: ctx.name, student_no: toInt(ctx.student && ctx.student.no), amount, submitted_at: serverTimestamp() });
    });
    return {};
  },
};
