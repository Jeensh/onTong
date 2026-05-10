"use client";

import { useEffect, useState } from "react";
import { Database, Loader2, RefreshCw, AlertCircle, CheckCircle2 } from "lucide-react";
import { getSeedStatus, seedDb, type SeedCounts } from "@/lib/simulation/seedApi";

const TABLES: { key: keyof SeedCounts; label: string }[] = [
  { key: "plant_mapping", label: "PlantMapping" },
  { key: "cast_spec", label: "CastSpec" },
  { key: "hr_spec", label: "HrSpec" },
  { key: "edging_group", label: "EdgingGroup" },
  { key: "edging_spec", label: "EdgingSpec" },
  { key: "hr_min_wgt", label: "HrMinWgt" },
  { key: "hr_max_wgt", label: "HrMaxWgt" },
  { key: "productivity_std", label: "ProductivityStd" },
  { key: "customer_std", label: "CustomerStd" },
  { key: "order_os", label: "주문 (OrderOS)" },
];

export function DbSeedCard() {
  const [counts, setCounts] = useState<SeedCounts | null>(null);
  const [loading, setLoading] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSeededAt, setLastSeededAt] = useState<Date | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await getSeedStatus();
      setCounts(r.counts);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setCounts(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const onSeed = async () => {
    if (!confirm("PostgreSQL DB 의 모든 마스터 + 주문 데이터를 초기화하고 fixtures default 로 다시 시드합니다. 계속할까요?")) {
      return;
    }
    setSeeding(true);
    setError(null);
    try {
      const r = await seedDb(true);
      setCounts(r.counts);
      setLastSeededAt(new Date());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSeeding(false);
    }
  };

  const totalRows = counts ? Object.values(counts).reduce((a, b) => a + b, 0) : 0;
  const isEmpty = counts !== null && totalRows === 0;

  return (
    <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Database size={18} className="text-emerald-500" />
          <h3 className="text-sm font-semibold text-foreground">PostgreSQL 시드 데이터</h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={refresh}
            disabled={loading || seeding}
            className="text-xs px-2.5 py-1.5 rounded border border-border hover:bg-muted/50 inline-flex items-center gap-1.5 disabled:opacity-50"
            title="현재 행 수 새로고침"
          >
            {loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
            새로고침
          </button>
          <button
            onClick={onSeed}
            disabled={seeding}
            className="text-xs px-2.5 py-1.5 rounded bg-emerald-500/90 text-white hover:bg-emerald-500 inline-flex items-center gap-1.5 disabled:opacity-50"
            title="기존 데이터 모두 초기화 후 fixtures default 로 시드"
          >
            {seeding ? <Loader2 size={12} className="animate-spin" /> : <Database size={12} />}
            DB 시드 초기화
          </button>
        </div>
      </div>

      {error ? (
        <div className="flex items-start gap-2 text-xs text-red-500 bg-red-500/5 border border-red-500/20 rounded p-2">
          <AlertCircle size={14} className="mt-0.5 flex-shrink-0" />
          <div className="leading-relaxed">
            {error}
            <br />
            <span className="text-muted-foreground">
              docker-compose 로 simulation-postgres 가 떠있는지 + SIM_DB_HOST 환경변수가 설정됐는지 확인.
            </span>
          </div>
        </div>
      ) : null}

      {counts ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-1.5 text-xs">
          {TABLES.map((t) => (
            <div
              key={t.key}
              className="rounded border border-border bg-card px-2 py-1.5 flex flex-col"
            >
              <span className="text-[10px] text-muted-foreground">{t.label}</span>
              <span className="font-mono font-semibold text-foreground">
                {counts[t.key]} <span className="text-[10px] text-muted-foreground font-normal">행</span>
              </span>
            </div>
          ))}
        </div>
      ) : null}

      {isEmpty ? (
        <p className="text-xs text-amber-500 flex items-center gap-1.5">
          <AlertCircle size={12} />
          DB 가 비어있습니다. 우측 「DB 시드 초기화」 버튼으로 시드하세요.
        </p>
      ) : counts && lastSeededAt ? (
        <p className="text-xs text-emerald-500 flex items-center gap-1.5">
          <CheckCircle2 size={12} />
          시드 완료 — 총 {totalRows}행 ({lastSeededAt.toLocaleTimeString()})
        </p>
      ) : null}
    </div>
  );
}
