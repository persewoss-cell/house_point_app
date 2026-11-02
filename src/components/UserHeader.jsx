// 가족 화면: 탭 위 통장/정보 요약
import React from "react";
import { useApp, useLoad } from "./ui.jsx";

export default function UserHeader({ onLogout, onPin }) {
  const app = useApp();
  const { data } = useLoad("user_header", {}, [app.ver]);
  const h = data && data.header;
  if (!h) return null;
  const items = [
    ["💰", "통장 잔액", `${h.balance} 포인트`, "c-mint"],
    ["🐷", "적금 총액", `${h.savings_total} 포인트`, "c-pink"],
    ["🪙", "투자 원금", `${h.inv_principal_total} 포인트`, "c-yellow", h.inv_principal_text],
    ["📈", "현재 평가", `${h.inv_eval_total} 포인트`, "c-blue", h.inv_eval_text],
    ["💼", "직업", h.role_name || "없음", "c-lav"],
  ];
  return (
    <div className="summary">
      <div className="sum-main">
        <div className="sum-name">
          {app.user && app.user.name}
          <small> 님</small>
        </div>
        <div className="sum-value">
          <span className="sum-label">🧮 총 자산</span>
          {h.asset_total}
          <small> 포인트</small>
        </div>
        <div className="sum-actions">
          <button type="button" onClick={onPin}>
            🔑 비밀번호 변경
          </button>
          <button type="button" onClick={onLogout}>
            ↪ 로그아웃
          </button>
        </div>
      </div>
      <div className="sum-grid">
        {items.map(([ic, label, value, c, sub]) => (
          <div className={`sum-item ${c}`} key={label}>
            <span className="sum-ic">{ic}</span>
            <div className="sum-txt">
              <div className="sum-k">{label}</div>
              <div className="sum-v">{value}</div>
              {sub ? <div className="sum-sub">{sub}</div> : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
