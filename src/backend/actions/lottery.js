// 🍀 복권 (기존 우리집 앱 데이터·계산 그대로)
// config/lottery_state · lottery_rounds · lottery_entries · lottery_winners · lottery_ledgers
// 1~20 중 4개 선택. 4개 맞으면 1등, 3개 2등, 2개 3등(고정 당첨금)
// 1·2등 상금 = (판매총액 − 3등 상금 합) × 등수 백분율 × (1 − 세금%) 를 당첨자 수로 나눔
import { find, getOne, set, update, ref, tx, where, orderBy, qlimit, serverTimestamp, batchWrite } from "../db.js";
import { fail, requireLogin, requireAdmin, requireStudent, ADMIN_NAME } from "../auth.js";
import { str, toInt, toDate, fmtLotteryDt, fmtKrDatetime } from "../../shared/format.js";

const STATE = ["config", "lottery_state"];
const ADMIN_SID = "__admin__";
const pad = (n, k = 2) => String(n).padStart(k, "0");
const orInt = (v, d) => toInt(v, 0) || d;
const halfUp = (x) => Math.floor(x + 0.5);
const priceOf = (r) => orInt(r.price ?? r.ticket_price, 20);

function normNums(nums) {
  const out = [];
  for (const n of nums || []) {
    const x = toInt(n, 0);
    if (x >= 1 && x <= 20 && !out.includes(x)) out.push(x);
  }
  return out.sort((a, b) => a - b);
}

async function getState() {
  return (await getOne(...STATE)) || {};
}

async function entriesOf(roundId) {
  const docs = await find("lottery_entries", where("round_id", "==", str(roundId)));
  return docs.map((x) => ({ ...x, _t: toDate(x.submitted_at) })).sort((a, b) => (a._t ? a._t.getTime() : 0) - (b._t ? b._t.getTime() : 0));
}

async function winnersOf(roundId) {
  const docs = await find("lottery_winners", where("round_id", "==", str(roundId)));
  const rk = (r) => toInt(String(r || "").replace("등", ""), 9);
  return docs
    .map((x) => ({
      rank: rk(x.rank),
      student_name: str(x.student_name),
      numbers: (x.numbers || []).map((n) => toInt(n)),
      prize: toInt(x.prize),
      is_admin: str(x.student_id) === ADMIN_SID,
    }))
    .sort((a, b) => a.rank - b.rank || a.student_name.localeCompare(b.student_name, "ko"));
}

function summaryOf(entries, price) {
  const people = new Set(entries.map((e) => str(e.student_id)).filter(Boolean));
  return [{ 참여자수: people.size, "참여 복권수": entries.length, "총 액수": entries.length * price }];
}

function entryRows(entries) {
  return entries.map((e) => {
    const nums = (e.numbers || []).map((n) => toInt(n));
    return {
      "참여 일시": fmtLotteryDt(e.submitted_at),
      이름: str(e.student_name),
      "복권 참여 번호": nums.map((n) => pad(n)).join(", "),
      _nums: nums,
      _admin: str(e.student_id) === ADMIN_SID,
    };
  });
}

async function roundView(rd, { withEntries = true } = {}) {
  const rid = String(rd._id);
  const win = (rd.draw_numbers || []).map((n) => toInt(n));
  const drawn = win.length === 4;
  const out = {
    round_id: rid,
    round_no: toInt(rd.round_no),
    status: drawn ? "drawn" : str(rd.status),
    winning_numbers: win,
    drawn_text: rd.drawn_at ? fmtKrDatetime(rd.drawn_at) : "",
    payout_done: !!rd.prizes_paid,
    ledger_applied: !!rd.ledger_reflected,
  };
  if (withEntries) {
    const ents = await entriesOf(rid);
    out.summary = summaryOf(ents, priceOf(rd));
    out.entries = entryRows(ents);
    out.winners = drawn ? await winnersOf(rid) : null;
  }
  return out;
}

// 당첨금 지급 (기존 api_pay_lottery_prizes)
async function payPrizes(roundId) {
  const docs = await find("lottery_winners", where("round_id", "==", str(roundId)));
  let count = 0;
  for (const w of docs) {
    if (w.paid) continue;
    const wRef = ref("lottery_winners", w._id);
    const sid = str(w.student_id);
    const prize = toInt(w.prize);
    if (!sid || prize <= 0 || sid === ADMIN_SID || sid.includes("/")) {
      await update("lottery_winners", w._id, { paid: true, paid_at: serverTimestamp() });
      continue;
    }
    const sRef = ref("students", sid);
    const tRef = ref("transactions");
    const paid = await tx(async (t) => {
      const ws = await t.get(wRef);
      if (!ws.exists() || ws.data().paid) return false;
      const s = await t.get(sRef);
      t.update(wRef, { paid: true, paid_at: serverTimestamp() });
      if (!s.exists()) return false;
      const nb = toInt(s.data().balance) + prize;
      t.update(sRef, { balance: nb });
      t.set(tRef, { student_id: sid, type: "lottery_prize", amount: prize, balance_after: nb, memo: `복권 당첨금 지급 ${toInt(w.round_no)}회차`, recorded_by_name: ADMIN_NAME, created_at: serverTimestamp() });
      return true;
    });
    if (paid) count += 1;
  }
  await update("lottery_rounds", roundId, { prizes_paid: true });
  return count;
}

// 장부 반영 (기존 api_reflect_lottery_ledger)
async function reflectLedger(roundId) {
  const rd = await getOne("lottery_rounds", roundId);
  if (rd.ledger_reflected) return;
  const ents = await entriesOf(roundId);
  const wins = await find("lottery_winners", where("round_id", "==", str(roundId)));
  const participants = new Set(ents.map((e) => str(e.student_id)).filter(Boolean)).size;
  const total = ents.length * priceOf(rd);
  const taxRate = orInt(rd.tax_rate, 40);
  let prizeTotal = 0;
  let third = 0;
  let n1 = 0;
  let n2 = 0;
  for (const w of wins) {
    const pz = toInt(w.prize);
    prizeTotal += pz;
    if (w.rank === "1등") n1 += 1;
    else if (w.rank === "2등") n2 += 1;
    else if (w.rank === "3등") third += pz;
  }
  const pool = Math.max(0, total - third);
  const tax = (n1 ? halfUp(pool * orInt(rd.first_pct, 80) * 0.01 * taxRate * 0.01) : 0) + (n2 ? halfUp(pool * orInt(rd.second_pct, 20) * 0.01 * taxRate * 0.01) : 0);
  await set("lottery_ledgers", `${roundId}`, {
    round_id: str(roundId),
    round_no: toInt(rd.round_no),
    draw_date: rd.drawn_at || rd.closed_at || null,
    participants,
    ticket_count: ents.length,
    total_amount: total,
    prize_total: prizeTotal,
    tax,
    social_donation: total - prizeTotal - tax,
    created_at: serverTimestamp(),
  });
  await update("lottery_rounds", roundId, { ledger_reflected: true, ledger_reflected_at: serverTimestamp() });
}

export default {
  async lottery_admin_load(ctx, { pick_round_id }) {
    requireAdmin(ctx);
    const [st, rounds, ledgerDocs] = await Promise.all([getState(), find("lottery_rounds", orderBy("round_no", "desc"), qlimit(50)), find("lottery_ledgers", orderBy("round_no", "desc"), qlimit(100))]);
    const open = st.active ? { round_id: str(st.round_id), round_no: toInt(st.round_no), ticket_price: orInt(st.price, 20) } : null;
    let counts = { admin: 0, student: 0, price: open ? open.ticket_price : 0 };
    if (open) {
      const ents = await entriesOf(open.round_id);
      counts = { admin: ents.filter((e) => str(e.student_id) === ADMIN_SID).length, student: ents.filter((e) => str(e.student_id) !== ADMIN_SID).length, price: open.ticket_price };
    }
    // 지금 다루는 회차: 진행 중이면 그 회차, 아니면 가장 최근 회차(마감 후 추첨·지급 단계)
    const curRd = st.round_id ? rounds.find((r) => String(r._id) === str(st.round_id)) : rounds[0];
    let current = null;
    if (curRd && str(curRd.status) !== "open") current = await roundView(curRd);
    else if (curRd) current = await roundView(curRd, { withEntries: false });
    const closed = rounds.filter((r) => str(r.status) === "closed").map((r) => ({ round_id: String(r._id), round_no: toInt(r.round_no) }));
    const pickRd = pick_round_id ? rounds.find((r) => String(r._id) === str(pick_round_id)) : null;
    const picked = pickRd ? await roundView(pickRd) : null;
    const ledger = ledgerDocs.map((x) => ({
      회차: toInt(x.round_no),
      복권추첨일: fmtKrDatetime(x.draw_date),
      "참여자 수": toInt(x.participants),
      "참여 복권 수": toInt(x.ticket_count),
      "총 액수": toInt(x.total_amount),
      "당첨금 지급 총액": toInt(x.prize_total) > 0 ? toInt(x.prize_total) : "-",
      세금: toInt(x.tax) > 0 ? toInt(x.tax) : "-",
      사회기부금: toInt(x.social_donation),
    }));
    return { open, counts, current, closed, picked, ledger };
  },

  async lottery_open(ctx, { ticket_price, tax_rate, first_pct, second_pct, third_prize }) {
    requireAdmin(ctx);
    const price = toInt(ticket_price);
    const tax = toInt(tax_rate);
    const p1 = toInt(first_pct);
    const p2 = toInt(second_pct);
    const p3 = toInt(third_prize);
    if (price <= 1) fail("복권 가격은 1보다 커야 합니다.");
    if (tax < 1 || tax > 100) fail("세금은 1~100 사이여야 합니다.");
    if (p1 + p2 !== 100) fail("1등/2등 백분율 합은 100이어야 합니다.");
    if (p3 < 0) fail("3등 당첨금은 0 이상이어야 합니다.");
    if ((await getState()).active) fail("이미 진행 중인 복권이 있습니다.");
    const top = (await find("lottery_rounds", orderBy("round_no", "desc"), qlimit(1)))[0];
    const round_no = toInt(top && top.round_no) + 1;
    const rRef = ref("lottery_rounds");
    const cfg = { price, tax_rate: tax, first_pct: p1, second_pct: p2, third_prize: p3 };
    await batchWrite([
      { type: "set", ref: rRef, data: { round_no, status: "open", ...cfg, opened_at: serverTimestamp(), closed_at: null, draw_numbers: [], drawn_at: null, prizes_paid: false, ledger_reflected: false } },
      { type: "set", ref: ref(...STATE), data: { active: true, round_id: rRef.id, round_no, ...cfg, draw_numbers: [], opened_at: serverTimestamp() } },
    ]);
    return { round_no };
  },

  async lottery_close(ctx) {
    requireAdmin(ctx);
    const st = await getState();
    if (!st.active) fail("진행 중인 복권이 없습니다.");
    await update("lottery_rounds", st.round_id, { status: "closed", closed_at: serverTimestamp() });
    await update(...STATE, { active: false });
    return {};
  },

  // 관리자 복권 참여 (번호 자동, 돈은 빠지지 않음)
  async lottery_admin_join(ctx, { count }) {
    requireAdmin(ctx);
    count = toInt(count);
    if (count <= 0) fail("참여 횟수는 1 이상이어야 합니다.");
    const st = await getState();
    if (!st.active) fail("개시된 복권이 없습니다.");
    const ops = [];
    for (let i = 0; i < count; i++) {
      const pool = Array.from({ length: 20 }, (_, k) => k + 1);
      const nums = [];
      while (nums.length < 4) nums.push(pool.splice(Math.floor(Math.random() * pool.length), 1)[0]);
      nums.sort((a, b) => a - b);
      ops.push({ type: "set", ref: ref("lottery_entries"), data: { round_id: str(st.round_id), round_no: toInt(st.round_no), student_id: ADMIN_SID, student_no: 0, student_name: ADMIN_NAME, numbers: nums, submitted_at: serverTimestamp(), ticket_price: orInt(st.price, 20) } });
    }
    await batchWrite(ops);
    return { count };
  },

  // 당첨번호 제출 → 당첨자 계산 (마감 후, 지급 전에는 다시 제출 가능)
  async lottery_draw(ctx, { round_id, numbers }) {
    requireAdmin(ctx);
    const nums = normNums(numbers);
    if (nums.length !== 4) fail("당첨번호는 1~20 중 중복 없이 4개여야 합니다.");
    const rd = await getOne("lottery_rounds", round_id);
    if (!rd) fail("회차 정보를 찾을 수 없습니다.");
    if (str(rd.status) !== "closed") fail("복권 마감 후 추첨할 수 있습니다.");
    if (rd.prizes_paid) fail("이미 당첨금을 지급한 회차예요.");
    const ents = await entriesOf(round_id);
    const third = orInt(rd.third_prize, 20);
    const price = priceOf(rd);
    const taxRate = orInt(rd.tax_rate, 40);
    const winners = [];
    let thirdTotal = 0;
    let n1 = 0;
    let n2 = 0;
    for (const e of ents) {
      const pick = (e.numbers || []).map((n) => toInt(n));
      const matched = pick.filter((n) => nums.includes(n)).sort((a, b) => a - b);
      const mc = matched.length;
      let rank = "";
      if (mc === 4) {
        rank = "1등";
        n1 += 1;
      } else if (mc === 3) {
        rank = "2등";
        n2 += 1;
      } else if (mc === 2) {
        rank = "3등";
        thirdTotal += third;
      }
      if (rank) winners.push({ e, matched, mc, rank });
    }
    const pool = Math.max(0, ents.length * price - thirdTotal);
    const firstTotal = halfUp(pool * orInt(rd.first_pct, 80) * 0.01 * (1 - taxRate * 0.01));
    const secondTotal = halfUp(pool * orInt(rd.second_pct, 20) * 0.01 * (1 - taxRate * 0.01));
    const each1 = n1 ? Math.trunc(firstTotal / n1) : 0;
    const each2 = n2 ? Math.trunc(secondTotal / n2) : 0;
    const old = await find("lottery_winners", where("round_id", "==", str(round_id)));
    const ops = old.map((d) => ({ type: "delete", ref: ref("lottery_winners", d._id) }));
    for (const w of winners) {
      const prize = w.rank === "1등" ? each1 : w.rank === "2등" ? each2 : third;
      ops.push({
        type: "set",
        ref: ref("lottery_winners", `${round_id}_${w.e._id}`),
        data: {
          round_id: str(round_id),
          round_no: toInt(rd.round_no),
          entry_id: String(w.e._id),
          rank: w.rank,
          prize,
          student_id: str(w.e.student_id),
          student_no: toInt(w.e.student_no),
          student_name: str(w.e.student_name),
          numbers: (w.e.numbers || []).map((n) => toInt(n)),
          matched_numbers: w.matched,
          match_count: w.mc,
          paid: false,
          created_at: serverTimestamp(),
        },
      });
    }
    ops.push({ type: "update", ref: ref("lottery_rounds", round_id), data: { draw_numbers: nums, drawn_at: serverTimestamp(), winners_calculated: true, gross_amount: ents.length * price, third_total: thirdTotal } });
    const st = await getState();
    if (str(st.round_id) === str(round_id)) ops.push({ type: "update", ref: ref(...STATE), data: { draw_numbers: nums } });
    await batchWrite(ops);
    return { winners: winners.length };
  },

  // 당첨금 지급 및 장부 반영
  async lottery_finalize(ctx, { round_id }) {
    requireAdmin(ctx);
    const rd = await getOne("lottery_rounds", round_id);
    if (!rd) fail("회차 정보를 찾을 수 없습니다.");
    if ((rd.draw_numbers || []).length !== 4) fail("당첨번호를 먼저 제출해 주세요.");
    if (rd.prizes_paid && rd.ledger_reflected) fail("이미 당첨금 지급 및 장부 반영이 끝난 회차예요.");
    const count = rd.prizes_paid ? 0 : await payPrizes(round_id);
    await reflectLedger(round_id);
    return { count };
  },

  async lottery_user_load(ctx) {
    requireLogin(ctx);
    const st = await getState();
    const open = st.active ? { round_id: str(st.round_id), round_no: toInt(st.round_no), ticket_price: orInt(st.price, 20) } : null;
    let history = [];
    if (open && ctx.sid) {
      const mine = (await entriesOf(open.round_id)).filter((e) => str(e.student_id) === ctx.sid);
      history = mine.map((e) => ({ 회차: toInt(e.round_no), "참여 일시": fmtLotteryDt(e.submitted_at), "복권 참여 번호": (e.numbers || []).map((n) => pad(toInt(n))).join(", ") }));
    }
    return { open, history };
  },

  // 복권 구매 (여러 게임 한 번에, 게임마다 통장 기록 1줄)
  async lottery_buy(ctx, { games }) {
    requireStudent(ctx);
    const list = (games || []).map(normNums);
    if (!list.length) fail("입력된 게임이 없습니다.");
    if (list.some((g) => g.length !== 4)) fail("1~20 숫자 중 중복 없이 4개를 선택해 주세요.");
    const st = await getState();
    if (!st.active || !st.round_id) fail("개시된 복권이 없습니다.");
    const rRef = ref("lottery_rounds", st.round_id);
    const sRef = ref("students", ctx.sid);
    await tx(async (t) => {
      const r = await t.get(rRef);
      if (!r.exists() || str(r.data().status) !== "open") fail("마감된 복권은 구매할 수 없습니다.");
      const rd = r.data();
      const price = priceOf(rd);
      const s = await t.get(sRef);
      let bal = toInt(s.data().balance);
      if (bal < price * list.length) fail("잔액이 부족하여 복권을 구매할 수 없습니다.");
      for (const nums of list) {
        bal -= price;
        t.set(ref("transactions"), { student_id: ctx.sid, type: "withdraw", amount: -price, balance_after: bal, memo: `복권 ${toInt(rd.round_no)}회 구매`, recorded_by_name: ctx.name, created_at: serverTimestamp() });
        t.set(ref("lottery_entries"), { round_id: str(st.round_id), round_no: toInt(rd.round_no), student_id: ctx.sid, student_no: toInt(ctx.student && ctx.student.no), student_name: ctx.name, numbers: nums, submitted_at: serverTimestamp(), ticket_price: price });
      }
      t.update(sRef, { balance: bal });
    });
    return { count: list.length };
  },
};
