// 📈 투자 : 종목/주가변동/관리장부/회수(지급)/투자하기/종목관리
// 기존 우리집 앱 계산 그대로: 주가는 소수 첫째 자리, 수익 = 투자금 × (현재가 − 매입가) ÷ 10, 차이가 −100 이하면 전액 손실
import { find, getOne, add, set, update, del, where, orderBy, qlimit, ref, tx, serverTimestamp, batchWrite } from "../db.js";
import { fail, requireLogin, requireAdmin, requireStudent, ADMIN_NAME } from "../auth.js";
import { applyTx } from "../core.js";
import { str, toInt, toFloat, toDate, fmtMd, fmtInvestDt } from "../../shared/format.js";

export const p1 = (v) => Number(toFloat(v, 0).toFixed(1));

// 기존 _calc_redeem_amount
export function redeemCalc(investAmount, buyPrice, sellPrice) {
  investAmount = toInt(investAmount);
  const diff = p1(p1(sellPrice) - p1(buyPrice));
  let profit;
  let redeem;
  if (diff <= -100) {
    profit = -investAmount;
    redeem = 0;
  } else {
    profit = (investAmount * diff) / 10;
    redeem = investAmount + profit;
    if (redeem < 0) redeem = 0;
  }
  return { diff, profit, redeem: Math.round(redeem) };
}

async function getProducts(activeOnly = true) {
  const docs = activeOnly ? await find("invest_products", where("is_active", "==", true)) : await find("invest_products");
  const out = [];
  for (const x of docs) {
    const nm = str(x.name).trim();
    if (!nm) continue;
    out.push({ product_id: String(x._id), name: nm, current_price: p1(x.current_price), is_active: x.is_active === undefined ? true : !!x.is_active });
  }
  out.sort((a, b) => a.name.localeCompare(b.name, "ko"));
  return out;
}

// 주가 변동 기록 (최신순). 색인이 없어도 되도록 종목으로만 거른 뒤 정렬
async function historyDocs(pid) {
  const docs = await find("invest_price_history", where("product_id", "==", String(pid)));
  return docs.map((x) => ({ ...x, _t: toDate(x.created_at) })).sort((a, b) => (b._t ? b._t.getTime() : 0) - (a._t ? a._t.getTime() : 0));
}

function histView(x) {
  return {
    id: String(x._id),
    dt_text: fmtInvestDt(x.created_at),
    reason: str(x.reason).trim(),
    price_before: p1(x.price_before ?? x.price ?? 0),
    price_after: p1(x.price_after ?? x.price ?? 0),
  };
}

// 주가 기록을 고치거나 지웠을 때: 다음 기록의 '변동 전 주가'를 이어 주고, 마지막 기록이면 현재 주가도 바꿈.
// 그 주가가 적용되던 동안 산 '아직 회수 안 한' 투자는 매입 주가도 새 값으로
async function relinkHistory(h, newPrice, all) {
  const pid = str(h.product_id);
  const asc = [...all].sort((a, b) => (a._t ? a._t.getTime() : 0) - (b._t ? b._t.getTime() : 0));
  const idx = asc.findIndex((x) => x._id === h._id);
  const next = asc.slice(idx + 1).find((x) => x._id !== h._id);
  if (next) await update("invest_price_history", next._id, { price_before: p1(newPrice) });
  else await set("invest_products", pid, { current_price: p1(newPrice), updated_at: serverTimestamp() }, true);
  const oldPrice = p1(h.price_after ?? h.price ?? 0);
  if (oldPrice === p1(newPrice)) return 0;
  const open = await find("invest_ledger", where("product_id", "==", pid));
  const ops = [];
  for (const x of open) {
    if (x.redeemed) continue;
    const bt = toDate(x.buy_at);
    if (!bt || !h._t || bt < h._t || (next && next._t && bt >= next._t)) continue;
    if (Math.abs(p1(x.buy_price) - oldPrice) > 0.05) continue;
    ops.push({ type: "update", ref: ref("invest_ledger", x._id), data: { buy_price: p1(newPrice) } });
  }
  await batchWrite(ops);
  return ops.length;
}

export default {
  async invest_load(ctx, { admin_mode }) {
    requireLogin(ctx);
    const adminLike = !!admin_mode && ctx.isAdmin;
    if (admin_mode && !adminLike) fail("권한이 없습니다.");
    const products = await getProducts(true);
    const histories = {};
    await Promise.all(
      products.map(async (p) => {
        histories[p.product_id] = (await historyDocs(p.product_id)).slice(0, 120).map(histView);
      })
    );
    const led = adminLike
      ? await find("invest_ledger", orderBy("buy_at", "desc"), qlimit(400))
      : (await find("invest_ledger", where("student_id", "==", ctx.sid))).sort((a, b) => (toDate(b.buy_at) || 0) - (toDate(a.buy_at) || 0));
    const priceBy = Object.fromEntries(products.map((p) => [p.product_id, p]));
    const ledger = led.map((x) => {
      const redeemed = !!x.redeemed;
      const row = {
        doc_id: String(x._id),
        student_id: str(x.student_id),
        product_id: str(x.product_id),
        name: str(x.name),
        product_name: str(x.product_name),
        buy_date_label: str(x.buy_date_label),
        buy_price: p1(x.buy_price),
        invest_amount: toInt(x.invest_amount),
        redeemed,
        sell_date_label: str(x.sell_date_label),
        sell_price: p1(x.sell_price),
        diff: p1(x.diff),
        profit: Math.round(toFloat(x.profit, 0)),
        redeem_amount: toInt(x.redeem_amount),
      };
      if (!redeemed) {
        const p = priceBy[row.product_id];
        const cur = p ? p.current_price : row.buy_price;
        const r = redeemCalc(row.invest_amount, row.buy_price, cur);
        row.cur_price = cur;
        row.proj_diff = r.diff;
        row.proj_profit = r.profit;
        row.proj_redeem = r.redeem;
      }
      return row;
    });
    let investEnabled = true;
    if (!ctx.isAdmin && ctx.student) investEnabled = ctx.student.invest_enabled === undefined || ctx.student.invest_enabled === null ? true : !!ctx.student.invest_enabled;
    const out = { products, histories, ledger, admin_like: adminLike, invest_enabled: investEnabled };
    if (adminLike) out.all_products = await getProducts(false);
    return out;
  },

  async invest_price_update(ctx, { product_id, reason, price }) {
    requireAdmin(ctx);
    reason = str(reason).trim();
    if (!reason) fail("변동 사유를 입력해 주세요.");
    const p = (await getProducts(true)).find((x) => x.product_id === String(product_id));
    if (!p) fail("종목을 찾지 못했어요.");
    await add("invest_price_history", { product_id: p.product_id, reason, price_before: p.current_price, price_after: p1(price), created_at: serverTimestamp() });
    await set("invest_products", p.product_id, { current_price: p1(price), updated_at: serverTimestamp() }, true);
    return {};
  },

  // ✏️ 주가 변동 기록 수정
  async invest_hist_update(ctx, { id, reason, price }) {
    requireAdmin(ctx);
    reason = str(reason).trim();
    if (!reason) fail("변동 사유를 입력해 주세요.");
    const h0 = await getOne("invest_price_history", id);
    if (!h0) fail("이미 지워졌거나 찾을 수 없는 기록이에요.");
    const all = await historyDocs(h0.product_id);
    const h = all.find((x) => x._id === h0._id);
    await update("invest_price_history", h._id, { reason, price_after: p1(price), updated_at: serverTimestamp() });
    return { repriced: await relinkHistory(h, price, all) };
  },

  // 🗑️ 주가 변동 기록 삭제: 그 앞 주가로 이어 붙임
  async invest_hist_delete(ctx, { id }) {
    requireAdmin(ctx);
    const h0 = await getOne("invest_price_history", id);
    if (!h0) fail("이미 지워졌거나 찾을 수 없는 기록이에요.");
    const all = await historyDocs(h0.product_id);
    const h = all.find((x) => x._id === h0._id);
    const i = all.indexOf(h);
    const prev = all[i + 1]; // 최신순이므로 다음 칸이 더 오래된 기록
    const back = prev ? p1(prev.price_after ?? prev.price) : p1(h.price_before ?? h.price);
    await del("invest_price_history", h._id);
    return { repriced: await relinkHistory(h, back, all) };
  },

  // 💸 투자 회수(지급)
  async invest_redeem(ctx, { doc_id }) {
    requireAdmin(ctx);
    const lRef = ref("invest_ledger", doc_id);
    const x = await getOne("invest_ledger", doc_id);
    if (!x) fail("투자 내역을 찾지 못했어요.");
    if (x.redeemed) fail("이미 지급 완료된 내역입니다.");
    const p = (await getProducts(false)).find((pp) => pp.product_id === str(x.product_id));
    const cur = p ? p.current_price : p1(x.buy_price);
    const r = redeemCalc(toInt(x.invest_amount), x.buy_price, cur);
    // 두 번 지급되지 않도록 먼저 선점
    const claimed = await tx(async (t) => {
      const s = await t.get(lRef);
      if (!s.exists() || s.data().redeemed) return false;
      t.update(lRef, { redeemed: true });
      return true;
    });
    if (!claimed) fail("이미 지급 완료된 내역입니다.");
    try {
      if (r.redeem > 0) await applyTx({ sid: str(x.student_id), memo: `투자 회수(${str(x.product_name)})`, amount: r.redeem, type: "deposit", recorder: ADMIN_NAME });
    } catch (e) {
      await update("invest_ledger", doc_id, { redeemed: false });
      throw e;
    }
    await update("invest_ledger", doc_id, {
      sell_at: serverTimestamp(),
      sell_date_label: fmtMd(new Date()),
      sell_price: cur,
      diff: r.diff,
      profit: r.profit,
      redeem_amount: r.redeem,
    });
    return {};
  },

  // 💳 투자하기 (가족)
  async invest_buy(ctx, { product_id, amount }) {
    requireStudent(ctx);
    amount = toInt(amount);
    const s = ctx.student;
    const enabled = s.invest_enabled === undefined || s.invest_enabled === null ? true : !!s.invest_enabled;
    if (!enabled) fail("이 계정은 현재 투자 기능이 비활성화되어 있어요.");
    if (amount <= 0) fail("투자 금액을 입력해 주세요.");
    const p = (await getProducts(true)).find((x) => x.product_id === String(product_id));
    if (!p) fail("투자 종목이 아직 없어요. 관리자에게 종목 추가를 요청해 주세요.");
    await applyTx({ sid: ctx.sid, memo: `투자 매입(${p.name})`, amount: -amount, type: "withdraw", recorder: str(s.name), checkBalance: true }).catch((e) => {
      if (String(e.userMessage || "").includes("잔액")) fail("통장 잔액보다 큰 액수는 투자할 수 없어요");
      throw e;
    });
    await add("invest_ledger", {
      student_id: ctx.sid,
      no: toInt(s.no),
      name: str(s.name),
      product_id: p.product_id,
      product_name: p.name,
      buy_at: serverTimestamp(),
      buy_date_label: fmtMd(new Date()),
      buy_price: p.current_price,
      invest_amount: amount,
      redeemed: false,
    });
    return {};
  },

  // 🧰 종목 추가/수정 (같은 이름의 삭제된 종목은 복구)
  async invest_product_save(ctx, { product_id, name, price }) {
    requireAdmin(ctx);
    const nm = str(name).trim();
    if (!nm) fail("종목명을 입력해 주세요.");
    const all = await getProducts(false);
    const key = nm.replace(/ /g, "").toLowerCase();
    const dup = all.find((p) => p.name.replace(/ /g, "").toLowerCase() === key);
    const payload = { name: nm, current_price: p1(price), is_active: true, updated_at: serverTimestamp() };
    if (!product_id && dup) {
      if (dup.is_active) fail("이미 같은 종목명이 있어요. (중복 추가 불가)");
      await set("invest_products", dup.product_id, payload, true);
      return { result: "restored" };
    }
    if (product_id && dup && dup.product_id !== String(product_id)) fail("이미 같은 종목명이 있어요. (중복 이름 불가)");
    if (!product_id) {
      await add("invest_products", { ...payload, created_at: serverTimestamp() });
      return { result: "added" };
    }
    await set("invest_products", String(product_id), payload, true);
    return { result: "updated" };
  },

  async invest_product_delete(ctx, { product_id }) {
    requireAdmin(ctx);
    if (!product_id) fail("종목을 선택해 주세요.");
    await set("invest_products", String(product_id), { is_active: false, updated_at: serverTimestamp() }, true);
    return {};
  },
};
