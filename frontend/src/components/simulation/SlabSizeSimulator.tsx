"use client";

// Slab 설계 시뮬레이터 — 3-pane 전체 래퍼
// 좌: 파라미터 컨트롤러 / 중: 3D 뷰어 / 우: 영향도 분석 패널

import dynamic from "next/dynamic";
import { useState, useEffect } from "react";
import { useSlabSimulator } from "@/lib/simulation/useSlabSimulator";
import { useSimulationStore } from "@/lib/simulation/useSimulationStore";
import { SlabParamController } from "./SlabParamController";
import { SlabImpactPanel } from "./SlabImpactPanel";
import { SlabCompareTable } from "./SlabCompareTable";
import type { SlabDesignResult } from "@/lib/simulation/types";

// Three.js는 SSR 불가 — dynamic import
const SlabDesignViewer3D = dynamic(
  () => import("./SlabDesignViewer3D").then((m) => m.SlabDesignViewer3D),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center w-full h-full bg-slate-950 text-slate-500 text-sm">
        3D 뷰어 로딩 중…
      </div>
    ),
  }
);

export function SlabSizeSimulator() {
  const {
    params,
    snapshotParams,
    result,
    constraints,
    isCalculating,
    error,
    updateParam,
    resetParams,
    saveSnapshot,
    getParamStatus,
    loadParams,
    loadFromOrder,
  } = useSlabSimulator();

  const { orders, pendingSlabParams, setPendingSlabParams } = useSimulationStore();

  // 다른 시나리오에서 딥링크로 진입 시 pendingSlabParams 적용
  useEffect(() => {
    if (!pendingSlabParams) return;
    loadParams(pendingSlabParams);
    setPendingSlabParams(null);
  }, [pendingSlabParams, loadParams, setPendingSlabParams]);

  // 스냅샷 저장 시 결과도 함께 보존
  const [snapshotResult, setSnapshotResult] = useState<SlabDesignResult | null>(null);
  const handleSaveSnapshot = () => {
    setSnapshotResult(result);
    saveSnapshot();
  };

  return (
    <div className="flex h-full overflow-hidden bg-slate-950">
      {/* 좌측: 파라미터 컨트롤러 (240px 고정) */}
      <div className="w-60 flex-shrink-0 border-r border-slate-800">
        <SlabParamController
          params={params}
          constraints={constraints}
          isCalculating={isCalculating}
          getParamStatus={getParamStatus}
          onUpdate={updateParam}
          onReset={resetParams}
          onSaveSnapshot={handleSaveSnapshot}
          orders={orders}
          onLoadOrder={loadFromOrder}
        />
      </div>

      {/* 중앙: 3D 뷰어 + 비교 테이블 */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* 3D 뷰어 */}
        <div className="flex-1 min-h-0">
          <SlabDesignViewer3D
            params={params}
            result={result}
            isCalculating={isCalculating}
          />
        </div>

        {/* 비교 테이블 (스냅샷 있을 때) */}
        {snapshotParams && (
          <div className="h-52 border-t border-slate-800 bg-slate-950 overflow-y-auto p-3">
            <SlabCompareTable
              before={snapshotParams}
              after={params}
              beforeResult={snapshotResult}
              afterResult={result}
            />
          </div>
        )}
      </div>

      {/* 우측: 영향도 분석 패널 (280px 고정) */}
      <div className="w-72 flex-shrink-0 border-l border-slate-800">
        <SlabImpactPanel result={result} isCalculating={isCalculating} />
      </div>

      {/* 에러 토스트 */}
      {error && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-red-800 text-white text-xs px-4 py-2 rounded shadow-lg">
          오류: {error}
        </div>
      )}
    </div>
  );
}
