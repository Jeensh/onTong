"use client";

// 좌측 파라미터 컨트롤러 — 슬라이더 + 숫자 입력 + 상태 인디케이터

import { useState } from "react";
import type { SlabSizeParams, SlabConstraints, Order } from "@/lib/simulation/types";

interface Props {
  params: SlabSizeParams;
  constraints: SlabConstraints | null;
  isCalculating: boolean;
  getParamStatus: (key: keyof SlabSizeParams) => "ok" | "warning" | "error";
  onUpdate: (key: keyof SlabSizeParams, value: number) => void;
  onReset: () => void;
  onSaveSnapshot: () => void;
  orders?: Order[];
  onLoadOrder?: (order: Order) => void;
}

const STATUS_BADGE: Record<string, string> = {
  ERROR: "text-red-400",
  DESIGNED: "text-green-400",
  PENDING: "text-yellow-400",
};

const STATUS_DOT: Record<string, string> = {
  ok: "bg-green-500",
  warning: "bg-yellow-400",
  error: "bg-red-500",
};

const PARAM_CONFIG: Array<{
  key: keyof SlabSizeParams;
  label: string;
  unit: string;
  step: number;
  description: string;
}> = [
  { key: "target_width",  label: "목표폭",  unit: "mm", step: 10, description: "1차 폭범위 산정 기준" },
  { key: "thickness",     label: "두께",    unit: "mm", step: 10, description: "연주설비 mold 두께" },
  { key: "target_length", label: "목표길이", unit: "mm", step: 100, description: "1차 길이범위 산정 기준" },
  { key: "unit_weight",   label: "단중",    unit: "kg", step: 100, description: "분할수 결정 Loop 제약" },
  { key: "split_count",   label: "분할수",  unit: "개", step: 1,   description: "Slab → 코일 분할 수" },
  { key: "yield_rate",    label: "실수율",  unit: "",   step: 0.001, description: "매수 산정 공식 사용" },
];

export function SlabParamController({
  params,
  constraints,
  isCalculating,
  getParamStatus,
  onUpdate,
  onReset,
  onSaveSnapshot,
  orders = [],
  onLoadOrder,
}: Props) {
  const [selectedOrderId, setSelectedOrderId] = useState<string>("");

  const handleOrderSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const orderId = e.target.value;
    setSelectedOrderId(orderId);
    if (!orderId || !onLoadOrder) return;
    const order = orders.find((o) => o.order_id === orderId);
    if (order) onLoadOrder(order);
  };

  return (
    <div className="flex flex-col h-full bg-slate-950 text-slate-100 p-3 gap-2 overflow-y-auto">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-semibold text-slate-300 tracking-wide uppercase">
          파라미터
        </span>
        {isCalculating && (
          <span className="text-[10px] text-indigo-400 animate-pulse">계산 중…</span>
        )}
      </div>

      {/* 주문 선택 드롭다운 */}
      {orders.length > 0 && (
        <div className="bg-slate-900 rounded-lg p-2.5 space-y-1">
          <div className="text-[10px] text-slate-500 font-medium uppercase tracking-wide">
            주문으로 불러오기
          </div>
          <select
            value={selectedOrderId}
            onChange={handleOrderSelect}
            className="w-full text-xs bg-slate-800 border border-slate-600 rounded px-2 py-1.5 text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value="">— 주문 선택 —</option>
            {orders.map((o) => (
              <option key={o.order_id} value={o.order_id}>
                {o.order_id}
                {o.error_code ? ` ⚠ ${o.error_code}` : ""}
                {" · "}{o.target_width}mm
              </option>
            ))}
          </select>
          {selectedOrderId && (() => {
            const o = orders.find((x) => x.order_id === selectedOrderId);
            if (!o) return null;
            return (
              <div className={`text-[10px] ${STATUS_BADGE[o.status] ?? "text-slate-400"}`}>
                {o.status === "ERROR" ? `❌ ${o.error_code}: ${o.error_msg ?? "설계 불가"}` :
                 o.status === "DESIGNED" ? `✅ 설계 완료 · 만족률 ${((o.satisfaction_rate ?? 0) * 100).toFixed(0)}%` :
                 "⏳ 대기 중"}
              </div>
            );
          })()}
        </div>
      )}

      {/* 파라미터 슬라이더 목록 */}
      {PARAM_CONFIG.map(({ key, label, unit, step, description }) => {
        const c = constraints?.[key as keyof SlabConstraints];
        const val = params[key] as number;
        const min = c?.min ?? 0;
        const max = c?.max ?? 100;
        const status = getParamStatus(key);
        const pct = max > min ? ((val - min) / (max - min)) * 100 : 50;

        return (
          <div key={key} className="bg-slate-900 rounded-lg p-2.5 space-y-1.5">
            {/* 라벨 행 */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span
                  className={`w-2 h-2 rounded-full flex-shrink-0 ${STATUS_DOT[status]}`}
                  title={status === "ok" ? "정상" : status === "warning" ? "경계 근접" : "범위 초과"}
                />
                <span className="text-xs font-medium text-slate-200">{label}</span>
                <span className="text-[10px] text-slate-500">{description}</span>
              </div>
              {/* 숫자 직접 입력 */}
              <div className="flex items-center gap-1">
                <input
                  type="number"
                  value={key === "yield_rate" ? val.toFixed(3) : val}
                  step={step}
                  min={min}
                  max={max}
                  onChange={(e) => {
                    const v = parseFloat(e.target.value);
                    if (!isNaN(v)) onUpdate(key, v);
                  }}
                  className={`w-20 text-right text-xs bg-slate-800 border rounded px-1.5 py-0.5 outline-none focus:ring-1
                    ${status === "error"
                      ? "border-red-500 text-red-300 focus:ring-red-500"
                      : status === "warning"
                      ? "border-yellow-500 text-yellow-200 focus:ring-yellow-500"
                      : "border-slate-600 text-slate-100 focus:ring-indigo-500"
                    }`}
                />
                <span className="text-[10px] text-slate-500 w-5">{unit}</span>
              </div>
            </div>

            {/* 슬라이더 */}
            <div className="relative">
              <div className="w-full h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-150 ${
                    status === "error"
                      ? "bg-red-500"
                      : status === "warning"
                      ? "bg-yellow-400"
                      : "bg-indigo-500"
                  }`}
                  style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
                />
              </div>
              <input
                type="range"
                min={min}
                max={max}
                step={step}
                value={val}
                onChange={(e) => onUpdate(key, parseFloat(e.target.value))}
                className="absolute inset-0 w-full opacity-0 cursor-pointer h-1.5"
                style={{ height: "6px", top: 0 }}
              />
            </div>

            {/* 범위 표시 */}
            {c && (
              <div className="flex justify-between text-[9px] text-slate-600">
                <span>{key === "yield_rate" ? c.min.toFixed(2) : c.min.toLocaleString()}</span>
                <span>{key === "yield_rate" ? c.max.toFixed(2) : c.max.toLocaleString()}</span>
              </div>
            )}
          </div>
        );
      })}

      {/* 하단 버튼 */}
      <div className="flex gap-2 mt-auto pt-2">
        <button
          onClick={onReset}
          className="flex-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 rounded py-1.5 transition-colors"
        >
          기준값 초기화
        </button>
        <button
          onClick={onSaveSnapshot}
          className="flex-1 text-xs bg-indigo-700 hover:bg-indigo-600 text-white rounded py-1.5 transition-colors"
        >
          이 설정 저장
        </button>
      </div>
    </div>
  );
}
