// Slab 설계 시뮬레이터 — 파라미터 상태 관리 + API 호출 훅

import { useState, useCallback, useEffect, useRef } from "react";
import type {
  SlabSizeParams,
  SlabDesignResult,
  SlabConstraints,
  Order,
} from "./types";
import { DEFAULT_SLAB_PARAMS } from "./types";

async function fetchConstraints(): Promise<SlabConstraints> {
  const res = await fetch("/api/simulation/slab/constraints");
  if (!res.ok) throw new Error("constraints fetch failed");
  return res.json();
}

async function fetchCalculation(params: SlabSizeParams): Promise<SlabDesignResult> {
  const res = await fetch("/api/simulation/slab/calculate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error("calculation failed");
  return res.json();
}

export function useSlabSimulator() {
  const [params, setParams] = useState<SlabSizeParams>(DEFAULT_SLAB_PARAMS);
  const [snapshotParams, setSnapshotParams] = useState<SlabSizeParams | null>(null);
  const [result, setResult] = useState<SlabDesignResult | null>(null);
  const [constraints, setConstraints] = useState<SlabConstraints | null>(null);
  const [isCalculating, setIsCalculating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // 설비 제약 기준 로드
  useEffect(() => {
    fetchConstraints()
      .then(setConstraints)
      .catch((e) => console.error("constraints load error:", e));
  }, []);

  // 파라미터 변경 시 즉시 계산
  const calculate = useCallback(async (p: SlabSizeParams) => {
    if (abortRef.current) abortRef.current.abort();
    abortRef.current = new AbortController();

    setIsCalculating(true);
    setError(null);
    try {
      const res = await fetchCalculation(p);
      setResult(res);
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setError(String(e));
      }
    } finally {
      setIsCalculating(false);
    }
  }, []);

  // 파라미터 업데이트
  const updateParam = useCallback(
    (key: keyof SlabSizeParams, value: number | string) => {
      setParams((prev) => {
        const next = { ...prev, [key]: value };
        calculate(next);
        return next;
      });
    },
    [calculate]
  );

  // 파라미터 직접 로드 (외부에서 세트 전체 교체)
  const loadParams = useCallback(
    (newParams: SlabSizeParams) => {
      setParams(newParams);
      calculate(newParams);
    },
    [calculate]
  );

  // 주문 데이터로부터 파라미터 로드
  const loadFromOrder = useCallback(
    (order: Order, overrides?: Partial<SlabSizeParams>) => {
      const unitWeight =
        order.slab_weight ??
        Math.round((order.order_weight_min + order.order_weight_max) / 2);
      const newParams: SlabSizeParams = {
        target_width: order.target_width,
        thickness: 250, // Slab 두께는 연주설비 mold 기준 고정
        target_length: order.target_length,
        unit_weight: unitWeight,
        split_count: order.split_count ?? 2,
        yield_rate: order.yield_rate,
        assigned_rolling: order.assigned_rolling,
        assigned_caster: order.assigned_caster,
        ...overrides,
      };
      loadParams(newParams);
    },
    [loadParams]
  );

  // 초기화
  const resetParams = useCallback(() => {
    setParams(DEFAULT_SLAB_PARAMS);
    calculate(DEFAULT_SLAB_PARAMS);
    setSnapshotParams(null);
  }, [calculate]);

  // 현재 설정 스냅샷 저장 (비교용)
  const saveSnapshot = useCallback(() => {
    setSnapshotParams({ ...params });
  }, [params]);

  // 초기 계산
  useEffect(() => {
    calculate(DEFAULT_SLAB_PARAMS);
  }, [calculate]);

  // 파라미터 값이 설비 범위 대비 어떤 상태인지 판단
  const getParamStatus = useCallback(
    (key: keyof SlabSizeParams): "ok" | "warning" | "error" => {
      if (!constraints) return "ok";
      const c = constraints[key as keyof SlabConstraints];
      if (!c) return "ok";
      const val = params[key] as number;
      if (val < c.min || val > c.max) return "error";
      const warnLow = c.min + (c.max - c.min) * 0.05;
      const warnHigh = c.max - (c.max - c.min) * 0.05;
      if (val < warnLow || val > warnHigh) return "warning";
      return "ok";
    },
    [params, constraints]
  );

  return {
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
  };
}
