"use client";

import { ArrowRight, GitBranch } from "lucide-react";

interface MigrationOutput {
  before: { castCd?: string; machineCd?: string; thickness?: string | null } | null;
  after: { castCd?: string; machineCd?: string; thickness?: string | null } | null;
  changed: boolean;
}

interface Props {
  output?: MigrationOutput | null;
  inputs?: Record<string, unknown>;
}

/** plant_mapping_migrate 결과를 직관적으로 시각화. PlantMapping 마이그레이션 시뮬 핵심 인사이트. */
export function MigrationDiffCard({ output, inputs }: Props) {
  if (!output) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-card p-4 text-xs text-muted-foreground">
        plant_mapping_migrate step 의 결과가 여기 표시됩니다. before / after / 깨지는지 한눈에.
      </div>
    );
  }

  const broken = output.after && output.after.thickness === null;
  const beforeOk = output.before && output.before.thickness !== null;

  return (
    <div className={`rounded-lg border p-4 space-y-3 ${
      output.changed
        ? "border-amber-500/30 bg-amber-500/5"
        : "border-emerald-500/30 bg-emerald-500/5"
    }`}>
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <GitBranch size={16} className={output.changed ? "text-amber-600" : "text-emerald-600"} />
          PlantMapping 마이그 시뮬 결과
        </h3>
        <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
          broken
            ? "bg-red-500/15 text-red-700 dark:text-red-300"
            : output.changed
            ? "bg-amber-500/15 text-amber-700 dark:text-amber-300"
            : "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
        }`}>
          {broken ? "★ 마이그 시 깨짐" : output.changed ? "변경 감지" : "변동 없음"}
        </span>
      </div>

      {inputs && (
        <div className="text-[10px] text-muted-foreground">
          smCd=<span className="font-mono">{String(inputs.smCd ?? "?")}</span>
          {" / "}productTypeCd=<span className="font-mono">{String(inputs.productTypeCd ?? "?")}</span>
        </div>
      )}

      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
        <div className="rounded border border-border bg-card p-3 space-y-1">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Before (default)</p>
          <Field label="castCd" value={output.before?.castCd ?? "—"} />
          <Field label="machineCd" value={output.before?.machineCd ?? "—"} />
          <Field
            label="thickness"
            value={output.before?.thickness ?? "—"}
            tone={beforeOk ? "ok" : "miss"}
          />
        </div>
        <ArrowRight size={20} className="text-muted-foreground" />
        <div className={`rounded border p-3 space-y-1 ${
          broken
            ? "border-red-500/40 bg-red-500/5"
            : output.changed
            ? "border-amber-500/40 bg-amber-500/5"
            : "border-border bg-card"
        }`}>
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">After (overrides)</p>
          <Field label="castCd" value={output.after?.castCd ?? "—"} highlight={output.changed} />
          <Field label="machineCd" value={output.after?.machineCd ?? "—"} highlight={output.changed} />
          <Field
            label="thickness"
            value={output.after?.thickness ?? "—"}
            tone={broken ? "miss" : "ok"}
          />
        </div>
      </div>

      {broken && (
        <div className="rounded border border-red-500/30 bg-red-500/10 p-2 text-[11px] text-red-700 dark:text-red-300">
          ⚠ 마이그 결과 castCd/machineCd 조합으로 CAST_SPEC 룩업 실패 →
          <b className="mx-1">이 매핑이 적용되면 해당 주문 두께 산정 불가</b>.
          fixture 에 신규 CAST_SPEC row 추가 또는 매핑 재검토 필요.
        </div>
      )}
      {!broken && output.changed && (
        <div className="rounded border border-amber-500/30 bg-amber-500/10 p-2 text-[11px] text-amber-700 dark:text-amber-300">
          매핑 변경됨. thickness 룩업은 정상이지만 운영 데이터 상 영향 주문 수를
          batch 시뮬로 확인하는 것을 권장.
        </div>
      )}
    </div>
  );
}

function Field({ label, value, tone, highlight }: {
  label: string; value: string | null;
  tone?: "ok" | "miss"; highlight?: boolean;
}) {
  const v = value ?? "—";
  const isMiss = tone === "miss" || v === "—" || v === null;
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className={`font-mono tabular-nums ${
        isMiss ? "text-red-600 dark:text-red-400 font-semibold" :
        tone === "ok" ? "text-emerald-700 dark:text-emerald-300 font-medium" :
        highlight ? "text-amber-700 dark:text-amber-400 font-medium" :
        "text-foreground"
      }`}>
        {v}
      </span>
    </div>
  );
}
