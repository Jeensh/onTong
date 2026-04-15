"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  Loader2,
  Play,
  RotateCcw,
  ArrowRight,
  TrendingUp,
  TrendingDown,
  Minus,
  ChevronDown,
  Zap,
} from "lucide-react";
import {
  engineGetParams,
  engineSimulate,
  type SimulationParam,
  type ParametricSimResult,
} from "@/lib/api/modeling";

interface SimulationPanelProps {
  repoId: string;
  initialEntityId?: string | null;
}

export function SimulationPanel({ repoId, initialEntityId }: SimulationPanelProps) {
  const [entityId, setEntityId] = useState(initialEntityId ?? "");
  const [params, setParams] = useState<SimulationParam[]>([]);
  const [localValues, setLocalValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ParametricSimResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingParams, setLoadingParams] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Known entities for the dropdown
  const KNOWN_ENTITIES = [
    { id: "com.ontong.scm.inventory.SafetyStockCalculator", label: "SafetyStockCalculator", desc: "안전재고 계산" },
    { id: "com.ontong.scm.inventory.InventoryManager", label: "InventoryManager", desc: "재고 관리" },
    { id: "com.ontong.scm.order.OrderService", label: "OrderService", desc: "주문 서비스" },
    { id: "com.ontong.scm.production.ProductionPlanner", label: "ProductionPlanner", desc: "생산 계획" },
    { id: "com.ontong.scm.production.WorkOrderProcessor", label: "WorkOrderProcessor", desc: "작업 지시" },
    { id: "com.ontong.scm.procurement.PurchaseOrderService", label: "PurchaseOrderService", desc: "구매 주문" },
    { id: "com.ontong.scm.procurement.SupplierEvaluator", label: "SupplierEvaluator", desc: "공급업체 평가" },
    { id: "com.ontong.scm.logistics.ShipmentTracker", label: "ShipmentTracker", desc: "배송 추적" },
    { id: "com.ontong.scm.logistics.WarehouseController", label: "WarehouseController", desc: "창고 관리" },
  ];

  const fetchParams = useCallback(async (eid: string) => {
    if (!eid) return;
    setLoadingParams(true);
    setError(null);
    setResult(null);
    try {
      const data = await engineGetParams(eid);
      setParams(data.params);
      const vals: Record<string, string> = {};
      for (const p of data.params) {
        vals[p.param_name] = p.default_value;
      }
      setLocalValues(vals);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoadingParams(false);
    }
  }, []);

  useEffect(() => {
    if (entityId) fetchParams(entityId);
  }, [entityId, fetchParams]);

  // Sync initialEntityId changes
  useEffect(() => {
    if (initialEntityId && initialEntityId !== entityId) {
      setEntityId(initialEntityId);
    }
  }, [initialEntityId]);

  const handleParamChange = (name: string, value: string) => {
    setLocalValues((prev) => ({ ...prev, [name]: value }));
  };

  const handleReset = () => {
    const vals: Record<string, string> = {};
    for (const p of params) {
      vals[p.param_name] = p.default_value;
    }
    setLocalValues(vals);
    setResult(null);
  };

  const handleSimulate = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await engineSimulate(entityId, repoId, localValues);
      setResult(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const hasChanges = params.some(
    (p) => localValues[p.param_name] !== p.default_value
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold mb-1">시뮬레이션</h2>
        <p className="text-sm text-muted-foreground">
          코드 엔티티의 파라미터를 변경하고 비즈니스 영향을 확인합니다.
        </p>
      </div>

      {/* Entity selector */}
      <div>
        <label className="text-xs text-muted-foreground">시뮬레이션 대상</label>
        <div className="relative mt-1">
          <select
            value={entityId}
            onChange={(e) => setEntityId(e.target.value)}
            className="w-full appearance-none px-3 py-2 pr-8 text-sm bg-background border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/30"
          >
            <option value="">엔티티를 선택하세요...</option>
            {KNOWN_ENTITIES.map((e) => (
              <option key={e.id} value={e.id}>
                {e.label} — {e.desc}
              </option>
            ))}
          </select>
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/20 p-3 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Loading params */}
      {loadingParams && (
        <div className="flex items-center justify-center py-8 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin mr-2" />
          <span className="text-sm">파라미터 로드 중...</span>
        </div>
      )}

      {/* Parameter sliders */}
      {params.length > 0 && !loadingParams && (
        <div className="rounded-lg border border-border bg-card p-4 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">파라미터 조정</span>
            <button
              onClick={handleReset}
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              <RotateCcw className="h-3 w-3" />
              초기화
            </button>
          </div>

          {params.map((p) => {
            if (p.param_type === "bool") {
              return (
                <div key={p.param_name} className="flex items-center justify-between">
                  <div>
                    <span className="text-sm font-mono">{p.param_name}</span>
                    <span className="text-xs text-muted-foreground ml-2">{p.description}</span>
                  </div>
                  <button
                    onClick={() =>
                      handleParamChange(
                        p.param_name,
                        localValues[p.param_name] === "true" ? "false" : "true"
                      )
                    }
                    className={`px-3 py-1 rounded text-xs font-medium ${
                      localValues[p.param_name] === "true"
                        ? "bg-green-100 dark:bg-green-950/40 text-green-700 dark:text-green-400"
                        : "bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-400"
                    }`}
                  >
                    {localValues[p.param_name] === "true" ? "ON" : "OFF"}
                  </button>
                </div>
              );
            }

            const isChanged = localValues[p.param_name] !== p.default_value;

            return (
              <div key={p.param_name}>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-mono">{p.param_name}</span>
                    <span className="text-xs text-muted-foreground">{p.description}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    {isChanged && (
                      <span className="text-xs text-muted-foreground line-through">
                        {p.default_value}
                      </span>
                    )}
                    <span className={`font-mono font-medium ${isChanged ? "text-primary" : ""}`}>
                      {localValues[p.param_name]}
                    </span>
                    {p.unit && <span className="text-xs text-muted-foreground">{p.unit}</span>}
                  </div>
                </div>
                {p.min_value && p.max_value && (
                  <input
                    type="range"
                    min={p.min_value}
                    max={p.max_value}
                    step={p.step ?? "1"}
                    value={localValues[p.param_name]}
                    onChange={(e) => handleParamChange(p.param_name, e.target.value)}
                    className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                  />
                )}
                {p.formula && (
                  <div className="text-[10px] text-muted-foreground mt-0.5 font-mono">
                    {p.formula}
                  </div>
                )}
              </div>
            );
          })}

          {/* Execute button */}
          <button
            onClick={handleSimulate}
            disabled={loading || !hasChanges}
            className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            {hasChanges ? "실행" : "파라미터를 변경하세요"}
          </button>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <div className="space-y-4">
          {/* Outputs */}
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="text-xs text-muted-foreground mb-3">시뮬레이션 결과</div>
            <div className="space-y-3">
              {result.outputs.map((o) => {
                const icon =
                  o.change_pct > 0 ? (
                    <TrendingUp className="h-4 w-4 text-blue-500" />
                  ) : o.change_pct < 0 ? (
                    <TrendingDown className="h-4 w-4 text-amber-500" />
                  ) : (
                    <Minus className="h-4 w-4 text-muted-foreground" />
                  );

                return (
                  <div key={o.metric_name} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {icon}
                      <span className="text-sm">{o.label}</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      <span className="text-muted-foreground">{o.before_value}{o.unit}</span>
                      <ArrowRight className="h-3 w-3 text-muted-foreground" />
                      <span className="font-medium">{o.after_value}{o.unit}</span>
                      <span
                        className={`text-xs px-1.5 py-0.5 rounded ${
                          o.change_pct > 0
                            ? "bg-blue-100 dark:bg-blue-950/40 text-blue-700 dark:text-blue-400"
                            : o.change_pct < 0
                            ? "bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400"
                            : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {o.change_pct > 0 ? "+" : ""}
                        {o.change_pct}%
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Affected processes */}
          {result.affected_processes.length > 0 && (
            <div className="rounded-lg border border-border bg-card p-4">
              <div className="text-xs text-muted-foreground mb-3">
                영향받는 프로세스 ({result.affected_processes.length}개)
              </div>
              <div className="space-y-2">
                {result.affected_processes.map((ap) => (
                  <div
                    key={ap.domain_id}
                    className="flex items-center justify-between rounded-md bg-muted/30 px-3 py-2"
                  >
                    <span className="text-sm font-medium">{ap.domain_name}</span>
                    <span className="text-xs text-muted-foreground">
                      {ap.distance === 0 ? "직접 매핑" : `거리: ${ap.distance}`}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Summary */}
          <div className="text-xs text-muted-foreground text-center">
            {result.message}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!entityId && !loadingParams && (
        <div className="text-center py-12 text-muted-foreground space-y-2">
          <Zap className="h-8 w-8 mx-auto mb-2 opacity-20" />
          <p className="text-sm">시뮬레이션할 엔티티를 선택하세요.</p>
          <p className="text-xs">
            분석 콘솔에서 영향분석 후 &ldquo;시뮬레이션 실행&rdquo;을 클릭하면 자동으로 연결됩니다.
          </p>
        </div>
      )}
    </div>
  );
}
