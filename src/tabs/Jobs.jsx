// 💼 직업/월급 (관리자): 공제 설정 · 월급 지급 설정 · 직업 지정/해제 · 목록 · 추가/수정/삭제 · 엑셀
import React, { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { readExcel, downloadExcel } from "../lib/excel.js";
import { useApp, useLoad, Cols, H3, Subheader, Caption, Btn, TextInput, Select, MultiSelect, NumberInput, Checkbox, Metric, Info, Warning, ErrorBox, Success, Expander, DataTable, Loading, ConfirmModal, ExcelBar, TplEditor, Popup, useSort, SortTh, moveItem } from "../components/ui.jsx";

const orInt = (v, d) => parseInt(v, 10) || d;
function calcNet(gross, cfg) {
  gross = parseInt(gross, 10) || 0;
  const x = gross * ((Number(cfg.tax_percent) || 10) / 100);
  const f = Math.floor(x);
  const tax = Math.abs(x - f - 0.5) < 1e-9 ? (f % 2 === 0 ? f : f + 1) : Math.round(x);
  return Math.max(0, gross - tax - orInt(cfg.desk_rent, 50) - orInt(cfg.electric_fee, 10) - orInt(cfg.health_fee, 10));
}

function DeductionCfg({ cfg, onSaved }) {
  const app = useApp();
  const [f, setF] = useState(cfg);
  useEffect(() => setF(cfg), [cfg]);
  const save = async () => {
    const r = await api("salary_cfg_save", f);
    if (r.ok) {
      app.toast("공제 설정 저장 완료!", "✅");
      onSaved();
    }
  };
  return (
    <Expander title="⚙️ 실수령액 계산식(공제 설정) 변경">
      <Cols w={[1.2, 1, 1, 1, 1.2]} va="bottom">
        <NumberInput label="세금(%)" min={0} max={100} step={0.5} decimals={1} value={f.tax_percent} onChange={(v) => setF((x) => ({ ...x, tax_percent: v }))} />
        <NumberInput label="자리임대료" min={0} value={f.desk_rent} onChange={(v) => setF((x) => ({ ...x, desk_rent: v }))} />
        <NumberInput label="전기세" min={0} value={f.electric_fee} onChange={(v) => setF((x) => ({ ...x, electric_fee: v }))} />
        <NumberInput label="건강보험료" min={0} value={f.health_fee} onChange={(v) => setF((x) => ({ ...x, health_fee: v }))} />
        <Btn onClick={save}>✅ 공제 설정 저장</Btn>
      </Cols>
    </Expander>
  );
}

function PayrollBox({ data, reload }) {
  const app = useApp();
  const [day, setDay] = useState(data.payroll.pay_day);
  const [auto, setAuto] = useState(data.payroll.auto_enabled);
  const [confirm, setConfirm] = useState(false);
  const [pin, setPin] = useState("");
  const [err, setErr] = useState("");
  const [warn, setWarn] = useState("");
  useEffect(() => {
    setDay(data.payroll.pay_day);
    setAuto(data.payroll.auto_enabled);
  }, [data.payroll.pay_day, data.payroll.auto_enabled]);

  const saveCfg = async () => {
    const r = await api("payroll_cfg_save", { pay_day: day, auto_enabled: auto });
    if (r.ok) {
      app.toast("월급 지급 설정 저장 완료!", "✅");
      reload();
    } else setErr(r.error);
  };
  const doPay = async (repay) => {
    setErr("");
    setWarn("");
    const r = await api("payroll_manual", { admin_pin: pin, confirm_repay: repay });
    if (!r.ok) return setErr(r.error);
    setConfirm(false);
    setPin("");
    if (r.paid > 0) app.toast(`월급 수동지급 완료: ${r.paid}명`, "💸");
    else app.toast("지급할 대상이 없어요. (직업 배정·월급을 확인해 주세요)", "ℹ️");
    if (r.err > 0) setWarn(`일부 지급 실패가 있었어요: ${r.err}건`);
    app.refresh();
  };
  return (
    <Expander title="💸 월급 지급 설정">
      <Cols w={[1, 0.9, 1, 2.4]} va="bottom">
        <NumberInput label="월급 지급 날짜: 매월 (일)" min={1} max={31} value={day} onChange={setDay} />
        <Checkbox
          label="자동지급"
          checked={auto}
          onChange={setAuto}
          help={"해당 날짜부터 매월, 직업 실수령액 기준으로 자동 지급합니다.\n그날 아무도 접속하지 않아도, 그 달 안에 누군가 접속하면 그때 지급됩니다.\n이미 이번 달에 지급한 사람은 건너뜁니다."}
        />
        <Btn onClick={saveCfg}>✅ 지급 설정 저장</Btn>
        <Btn onClick={() => (data.already_any ? setConfirm(true) : doPay(false))}>💸 수동지급(이번 달 즉시 지급)</Btn>
      </Cols>
      <Caption>• 수동지급: 이번 달(현재 월)에 즉시 지급합니다. 이미 지급한 기록이 있으면 확인 후 재지급합니다.</Caption>
      <ConfirmModal
        open={confirm}
        title="💸 월급 재지급"
        message="이번 달에 이미 월급 지급(자동/수동)한 기록이 있어요. 그래도 지급할까요?"
        yesText="지급"
        noText="취소"
        onYes={() => doPay(true)}
        onNo={() => {
          setConfirm(false);
          setErr("");
          app.toast("수동지급 취소", "🛑");
        }}
      >
        <TextInput label="관리자 비밀번호" type="password" value={pin} onChange={setPin} onEnter={() => doPay(true)} />
        <ErrorBox>{confirm ? err : ""}</ErrorBox>
      </ConfirmModal>
      <ErrorBox>{confirm ? "" : err}</ErrorBox>
      {warn ? <Warning>{warn}</Warning> : null}
    </Expander>
  );
}

// 📋 직업/월급 목록 (가족별 배정)
function assignmentRows(data) {
  const idTo = Object.fromEntries(data.students.map((s) => [s.student_id, s]));
  const rows = [];
  for (const r of data.rows) {
    for (const sid of r.assigned_ids) {
      const s = idTo[sid];
      if (!s) continue;
      rows.push({ key: `${r._id}|${sid}`, job_id: r._id, sid, 이름: s.name, 직업: r.job, 월급: r.salary, 실수령액: calcNet(r.salary, data.cfg) });
    }
  }
  rows.sort((a, b) => a.이름.localeCompare(b.이름, "ko") || a.직업.localeCompare(b.직업, "ko"));
  return rows;
}

// 해제 팝업: 배정 목록에서 체크한 것만 해제
function FirePopup({ data, open, onClose, onDone }) {
  const rows = assignmentRows(data);
  const srt = useSort(rows);
  const [chk, setChk] = useState({});
  const [err, setErr] = useState("");
  const all = rows.length > 0 && rows.every((r) => chk[r.key]);
  const run = async () => {
    setErr("");
    const picked = rows.filter((r) => chk[r.key]);
    if (!picked.length) return setErr("해제할 가족을 체크해 주세요.");
    const byJob = {};
    picked.forEach((r) => (byJob[r.job_id] = [...(byJob[r.job_id] || []), r.sid]));
    for (const [job_id, sids] of Object.entries(byJob)) {
      const r = await api("job_assign", { job_id, op: "fire", sids });
      if (!r.ok) return setErr(r.error || "해제 실패");
    }
    setChk({});
    onDone(picked.length);
  };
  return (
    <Popup open={open} title="➖ 직업 해제" onClose={onClose}>
      {!rows.length ? (
        <Info>아직 직업이 배정된 가족이 없습니다.</Info>
      ) : (
        <>
          <div className="tbl-wrap">
            <div className="tbl-scroll" style={{ maxHeight: 380 }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th style={{ width: "3.2rem" }}>
                      <Checkbox label="" checked={all} onChange={(v) => setChk(v ? Object.fromEntries(rows.map((r) => [r.key, true])) : {})} />
                    </th>
                    {["이름", "직업", "월급", "실수령액"].map((c) => (
                      <SortTh key={c} label={c} s={srt} />
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {srt.sorted.map((r) => (
                    <tr key={r.key} onClick={() => setChk((c) => ({ ...c, [r.key]: !c[r.key] }))} style={{ cursor: "pointer" }}>
                      <td onClick={(e) => e.stopPropagation()}>
                        <Checkbox label="" checked={!!chk[r.key]} onChange={(v) => setChk((c) => ({ ...c, [r.key]: v }))} />
                      </td>
                      <td>{r.이름}</td>
                      <td>{r.직업}</td>
                      <td>{r.월급}</td>
                      <td>{r.실수령액}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <Cols w={[3, 1]} va="center">
            <div className="caption">{`맨 위 체크칸을 누르면 전체 선택 · ${Object.values(chk).filter(Boolean).length}개 선택됨`}</div>
            <Btn onClick={run}>➖ 체크한 직업 해제</Btn>
          </Cols>
        </>
      )}
      <ErrorBox>{err}</ErrorBox>
    </Popup>
  );
}

function JobAssign({ data, reload }) {
  const app = useApp();
  const accOptions = data.students.map((r) => r.name);
  const labelToId = Object.fromEntries(data.students.map((r) => [r.name, r.student_id]));
  const jobOptions = data.rows.map((r) => ({ value: r._id, label: `${r.order} | ${r.job} (월급 ${r.salary})` }));
  const jobIds = jobOptions.map((o) => o.value);
  const [job, setJob] = useState(jobIds[0] || null);
  const [sel, setSel] = useState([]);
  const [msg, setMsg] = useState(null);
  const [fireOpen, setFireOpen] = useState(false);
  const [clearAsk, setClearAsk] = useState(false);
  useEffect(() => {
    if (!job || !jobIds.includes(job)) setJob(jobIds[0] || null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobIds.join("|")]);

  const hire = async () => {
    setMsg(null);
    if (!job) return setMsg(["warning", "먼저 직업을 선택하세요."]);
    if (!sel.length) return setMsg(["warning", "대상 가족을 선택하세요."]);
    const r = await api("job_assign", { job_id: job, op: "hire", sids: sel.map((l) => labelToId[l]).filter(Boolean) });
    if (!r.ok) return setMsg(["error", r.error]);
    if (r.changed) {
      app.toast("고용 완료!", "✅");
      setSel([]);
      reload();
    } else setMsg(["info", "변경된 내용이 없습니다. (이미 배정됨)"]);
  };
  const clearAll = async () => {
    setClearAsk(false);
    const r = await api("job_clear_all", {});
    if (!r.ok) return setMsg(["error", r.error]);
    app.toast("전체 직업 해제 완료!", "✅");
    reload();
  };

  return (
    <>
      <H3>🎖️ 직업 지정 / 회수</H3>
      <Caption>직업을 고른 뒤 가족을 선택하고 ‘고용’을 누르세요. (정원 제한 없음, 한 사람이 여러 직업 가능)</Caption>
      <Cols w={[2, 2.6, 0.8, 0.8, 1]} va="bottom">
        {jobOptions.length ? (
          <Select
            label="부여할 직업 선택"
            value={job}
            options={jobOptions}
            onChange={setJob}
            onMove={async (i, d) => {
              const r = await api("job_reorder", { ids: moveItem(jobIds, i, d) });
              if (r.ok) await reload();
              else setMsg(["error", r.error || "순서 변경 실패"]);
            }}
          />
        ) : (
          <span />
        )}
        <MultiSelect label="대상 가족 선택(여러 명 가능)" value={sel} options={accOptions} onChange={setSel} />
        <Btn onClick={hire}>➕ 고용</Btn>
        <Btn onClick={() => setFireOpen(true)}>➖ 해제</Btn>
        <Btn onClick={() => setClearAsk(true)}>🔥 전체 해제</Btn>
      </Cols>
      {msg ? msg[0] === "warning" ? <Warning>{msg[1]}</Warning> : msg[0] === "info" ? <Info>{msg[1]}</Info> : <ErrorBox>{msg[1]}</ErrorBox> : null}
      <ConfirmModal open={clearAsk} title="🔥 전체 직업 해제" message="모든 가족의 직업 배정을 해제할까요?" onYes={clearAll} onNo={() => setClearAsk(false)} />
      <FirePopup
        data={data}
        open={fireOpen}
        onClose={() => setFireOpen(false)}
        onDone={(n) => {
          setFireOpen(false);
          app.toast(`해제 완료! (${n}개)`, "✅");
          reload();
        }}
      />
    </>
  );
}

function JobEdit({ data, reload }) {
  return (
    <>
      <H3>➕ 직업 추가 / 수정 / 삭제</H3>
      <TplEditor
        noun="직업"
        items={data.rows}
        itemLabel={(r) => `${r.order} | ${r.job} (월급 ${r.salary})`}
        blank={() => ({ job: "", salary: 0 })}
        fromItem={(r) => ({ job: r.job, salary: r.salary })}
        widths={[2.4, 1.2, 1.2]}
        fields={(f, set) => [
          <TextInput key="j" label="직업" value={f.job} onChange={(v) => set({ job: v })} />,
          <NumberInput key="s" label="월급" min={0} stepper={false} value={f.salary} onChange={(v) => set({ salary: v })} />,
          <Metric key="n" label="실수령액(자동)" value={calcNet(f.salary, data.cfg)} />,
        ]}
        onSave={async (f, edit) => {
          if (!f.job.trim()) return { ok: false, error: "직업을 입력해 주세요." };
          return api("job_save", { job_id: edit ? edit._id : "", job: f.job.trim(), salary: f.salary });
        }}
        onDelete={(r) => api("job_delete", { job_id: r._id })}
        idOf={(r) => r._id}
        onReorder={(ids) => api("job_reorder", { ids })}
        saveToast="저장 완료!"
        deleteToast="삭제 완료"
        reload={reload}
      />
    </>
  );
}

function JobExcel({ data, reload }) {
  const app = useApp();
  const COLS = ["순", "직업", "월급"];
  const [wipe, setWipe] = useState(false);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [msgs, setMsgs] = useState([]);
  const [err, setErr] = useState("");
  const onFile = async (fl) => {
    setFile(fl);
    setMsgs([]);
    setPreview(null);
    if (!fl) return;
    try {
      const { columns, rows } = await readExcel(fl);
      if (!COLS.every((c) => columns.includes(c))) return setMsgs(["엑셀 컬럼은 반드시: 순 | 직업 | 월급 이어야 합니다."]);
      const num = (v, d) => {
        const n = Number(v);
        return v === undefined || v === null || v === "" || !Number.isFinite(n) ? d : Math.trunc(n);
      };
      const df = rows
        .map((r) => ({ 순: num(r["순"], 0), 직업: r["직업"] === undefined || r["직업"] === null ? "" : String(r["직업"]).trim(), 월급: num(r["월급"], 0) }))
        .filter((r) => r.순 > 0 && r.월급 >= 0 && r.직업);
      if (!df.length) return setMsgs(["❌ 올바른 행이 없어요. (순은 1 이상, 직업명 필수, 월급 0 이상)"]);
      df.sort((a, b) => a.순 - b.순);
      setPreview(df);
    } catch (e) {
      setMsgs([`직업 엑셀 읽기 실패: ${e.message || e}`]);
    }
  };
  const save = async () => {
    setErr("");
    if (!preview || !preview.length) return setErr("먼저 올바른 엑셀을 업로드해서 미리보기를 만든 뒤 저장하세요.");
    const r = await api("jobs_bulk_save", { rows: preview, wipe });
    if (r.ok) {
      app.toast("직업 엑셀 저장(반영) 완료!", "📥");
      setPreview(null);
      setFile(null);
      reload();
    } else setErr(`직업 엑셀 저장 실패: ${r.error}`);
  };
  const current = data.rows.map((r) => ({ 순: r.order, 직업: String(r.job).trim(), 월급: r.salary }));
  return (
    <>
      <H3>📥 직업 엑셀 일괄 업로드</H3>
      <ExcelBar
        downloads={[
          ["📄 샘플 엑셀", () => downloadExcel("jobs_sample.xlsx", [{ name: "jobs", columns: COLS, rows: [{ 순: 1, 직업: "설거지 담당", 월급: 500 }, { 순: 2, 직업: "분리수거 담당", 월급: 300 }] }])],
          ["📄 현재 직업 엑셀", () => downloadExcel("jobs_current.xlsx", [{ name: "jobs", columns: COLS, rows: current }])],
        ]}
        file={file}
        onFile={onFile}
        overwrite={wipe}
        setOverwrite={setWipe}
        overwriteLabel="⚠️ 기존 직업 목록을 모두 지우고 엑셀로 덮어쓰기"
        onSave={save}
        saveText="✅ 저장(반영)"
      >
        {msgs.map((m) => (
          <ErrorBox key={m}>{m}</ErrorBox>
        ))}
        {preview ? <Success>{`미리보기 준비 완료! (${preview.length}행) 저장(반영)을 누르세요.`}</Success> : null}
        {preview && preview.length ? <DataTable rows={preview} columns={COLS} /> : null}
      </ExcelBar>
      <ErrorBox>{err}</ErrorBox>
    </>
  );
}

export default function Jobs() {
  const app = useApp();
  const { data, error, reload } = useLoad("jobs_load", {}, [app.ver]);
  return (
    <>
      <Subheader>💼 직업/월급 시스템</Subheader>
      {error ? <ErrorBox>{error}</ErrorBox> : null}
      {!data && !error ? <Loading /> : null}
      {data ? (
        <>
          <DeductionCfg cfg={data.cfg} onSaved={reload} />
          <PayrollBox data={data} reload={reload} />
          <JobAssign data={data} reload={reload} />
          <H3>📋 직업/월급 목록</H3>
          {(() => {
            const rows = assignmentRows(data);
            return rows.length ? <DataTable rows={rows} columns={["이름", "직업", "월급", "실수령액"]} csvName="직업월급" /> : <Info>아직 직업이 배정된 가족이 없습니다.</Info>;
          })()}
          <JobEdit data={data} reload={reload} />
          <JobExcel data={data} reload={reload} />
        </>
      ) : null}
    </>
  );
}
