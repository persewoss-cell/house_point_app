// 🏦 적금 (가족): 적금 가입 · 내 적금 내역 · 중도 해지 · 이자율표
import React, { useEffect, useRef, useState } from "react";
import { api } from "../lib/api.js";
import { useApp, useLoad, Cols, H3, H4, Caption, Btn, Select, NumberInput, Metric, Info, Warning, ErrorBox, DataTable, Loading, ConfirmModal } from "../components/ui.jsx";

const WEEKS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
const MY_COLS = ["적금기간", "이자율", "적금 금액", "이자", "만기금액", "적금날짜", "만기날짜", "처리결과", "지급금액"];
const pyRound = (x) => {
  const f = Math.floor(x);
  return Math.abs(x - f - 0.5) < 1e-9 ? (f % 2 === 0 ? f : f + 1) : Math.round(x);
};

function RateTable() {
  const rows = WEEKS.map((w) => ({ 기간: `${w}주`, 이자율: `${w * 5}%`, "100포인트 넣으면": `${100 + w * 5}포인트` }));
  return (
    <>
      <H3>📊 이자율표</H3>
      <DataTable rows={rows} columns={["기간", "이자율", "100포인트 넣으면"]} small />
    </>
  );
}

export function SavingsList({ rows }) {
  if (!rows || !rows.length) return <Info>적금 내역이 없어요.</Info>;
  return <DataTable rows={rows} columns={MY_COLS} csvName="적금내역" />;
}

export default function Savings() {
  const app = useApp();
  const { data, error } = useLoad("savings_load", {}, [app.ver]);
  const [w, setW] = useState(5);
  const [principal, setPrincipal] = useState(100);
  const [err, setErr] = useState("");
  const [askJoin, setAskJoin] = useState(false);
  const [pick, setPick] = useState("(선택 없음)");
  const [askCancel, setAskCancel] = useState(false);
  const [cErr, setCErr] = useState("");
  const toasted = useRef(false);
  useEffect(() => {
    if (data && data.auto_matured > 0 && !toasted.current) {
      toasted.current = true;
      app.toast(`적금 만기 지급: ${data.auto_matured}건`, "🏦");
      app.refresh();
    }
  }, [data, app]);

  if (error && !data) return <ErrorBox>{error}</ErrorBox>;
  if (!data) return <Loading />;

  const p = parseInt(principal, 10) || 0;
  const interest = pyRound(p * w * 0.05);
  const mat = p + interest;
  const due = new Date(Date.now() + w * 7 * 86400000);
  const dueText = `${due.getFullYear()}-${String(due.getMonth() + 1).padStart(2, "0")}-${String(due.getDate()).padStart(2, "0")}`;
  const over = p > data.balance;

  const join = async () => {
    setAskJoin(false);
    setErr("");
    const r = await api("savings_join", { weeks: w, principal: p });
    if (r.ok) {
      app.toast("적금 가입 완료!", "💰");
      app.refresh();
    } else setErr(r.error || "적금 가입 실패");
  };

  const rows = data.rows || [];
  const running = rows.filter((r) => r._status === "active");
  const opts = ["(선택 없음)", ...running.map((r) => `${r.적금기간} | 원금 ${r["적금 금액"]} | 만기 ${r.만기날짜}`)];
  const cancel = async () => {
    setAskCancel(false);
    setCErr("");
    const r = running[opts.indexOf(pick) - 1];
    if (!r) return;
    const res = await api("savings_cancel", { doc_id: r._id });
    if (res.ok) {
      app.toast(`해지 완료! (+${res.refunded})`, "🧾");
      setPick("(선택 없음)");
      app.refresh();
    } else setCErr(res.error || "해지 실패");
  };

  return (
    <>
      <H3>💰 적금 넣기</H3>
      <Caption>• 적금에 넣으면 통장에서 빠져나가요. • 만기가 되면 원금+이자가 자동으로 들어와요. • 중도 해지하면 원금만 돌려받아요.</Caption>
      <Cols w={[1, 1.3, 1.6, 1.1]} va="bottom">
        <Select label="기간(1~10주)" value={w} options={WEEKS.map((x) => ({ value: x, label: `${x}주` }))} onChange={(v) => setW(parseInt(v, 10))} />
        <NumberInput label="적금 원금(10단위)" min={10} step={10} value={principal} onChange={setPrincipal} />
        <Metric label="미리보기(이자율 / 만기 수령액)" value={`${w * 5}% / ${mat}P`} />
        <Btn
          disabled={over}
          onClick={() => {
            setErr("");
            if (!(p > 0)) return setErr("적금 원금을 입력해 주세요.");
            if (p % 10 !== 0) return setErr("원금은 10단위만 가능합니다.");
            setAskJoin(true);
          }}
        >
          🐷 적금 가입
        </Btn>
      </Cols>
      <Caption>{`만기일: ${dueText} · 만기 수령액 ${mat}포인트 (원금 ${p} + 이자 ${interest})`}</Caption>
      {over ? <Warning>⚠️ 현재 잔액({data.balance}포인트)보다 원금이 커서 가입할 수 없어요.</Warning> : null}
      <ErrorBox>{err}</ErrorBox>
      <ConfirmModal open={askJoin} title="🐷 적금 가입" message={`${p}포인트를 ${w}주 적금에 넣을까요?`} onYes={join} onNo={() => setAskJoin(false)}>
        <div className="caption center">{`통장에서 ${p}포인트가 빠져나가고, ${dueText}에 ${mat}포인트(이자율 ${w * 5}%)를 받아요.`}</div>
      </ConfirmModal>

      <H3>📒 내 적금 내역</H3>
      <SavingsList rows={rows} />
      {running.length ? (
        <>
          <H4>⚠️ 중도 해지(원금만 지급)</H4>
          <Cols w={[3, 1]} va="bottom">
            <Select label="중도 해지할 적금" hideLabel value={pick} options={opts} onChange={setPick} />
            <Btn onClick={() => setAskCancel(true)} disabled={pick === "(선택 없음)"}>
              중도해지
            </Btn>
          </Cols>
          <ErrorBox>{cErr}</ErrorBox>
          <ConfirmModal open={askCancel} title="⚠️ 적금 중도해지" message={`${pick}\n이 적금을 해지할까요?`} onYes={cancel} onNo={() => setAskCancel(false)}>
            <div className="caption center">원금만 돌려받고 이자는 없어져요.</div>
          </ConfirmModal>
        </>
      ) : null}
      <RateTable />
    </>
  );
}
