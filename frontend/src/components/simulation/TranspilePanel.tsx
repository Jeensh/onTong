"use client";

import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Code2,
  Loader2,
  Sparkles,
  Save,
  Wand2,
  XCircle,
} from "lucide-react";
import {
  listMethods,
  previewTranspile,
  saveTranspiled,
  type MethodInfo,
  type PreviewResponse,
} from "@/lib/simulation/transpileApi";
import { HelpPopover } from "./HelpPopover";

const SAMPLE_JAVA_FILES = [
  {
    label: "SdThicknessAction (Step 1 — 두께)",
    path: "sample-repos/slab-design/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/action/SdThicknessAction.java",
    referenceStep: "thickness",
  },
  {
    label: "SdSlabCountAction (Step 9 — Slab 매수)",
    path: "sample-repos/slab-design/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/action/SdSlabCountAction.java",
    referenceStep: "slab_count",
  },
];

export function TranspilePanel() {
  const [filePath, setFilePath] = useState(SAMPLE_JAVA_FILES[0].path);
  const [referenceStep, setReferenceStep] = useState(SAMPLE_JAVA_FILES[0].referenceStep);
  const [methods, setMethods] = useState<MethodInfo[]>([]);
  const [methodName, setMethodName] = useState<string>("");
  const [className, setClassName] = useState<string>("");
  const [targetStepId, setTargetStepId] = useState<string>("");
  const [preferLlm, setPreferLlm] = useState(true);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [loadingList, setLoadingList] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedPath, setSavedPath] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const onLoadMethods = async () => {
    setLoadingList(true);
    setErr(null);
    setMethods([]);
    setMethodName("");
    setPreview(null);
    setSavedPath(null);
    try {
      const list = await listMethods(filePath);
      setMethods(list);
      // 가장 길어 보이는 public 메서드를 기본 선택 (대개 entry-point)
      const candidate =
        list.find((m) => m.method_name === "execute") ?? list[0];
      if (candidate) {
        setMethodName(candidate.method_name);
        setClassName(candidate.class_name);
      }
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoadingList(false);
    }
  };

  const onPreview = async () => {
    if (!filePath || !methodName) {
      setErr("자바 파일 + 메서드를 모두 선택하세요.");
      return;
    }
    setLoadingPreview(true);
    setErr(null);
    setPreview(null);
    setSavedPath(null);
    try {
      const result = await previewTranspile({
        java_path: filePath,
        method_name: methodName,
        class_name: className || undefined,
        target_step_id: targetStepId || undefined,
        reference_step_id: referenceStep || undefined,
        // shadow 비교용 샘플: 비어 있어도 백엔드가 structural 로 자동 fallback.
        sample_inputs: referenceStep
          ? [
              { order: { confirmedPlantCd: "KKKK    ", productTypeCd: "A001" }, slab: {} },
              { order: { confirmedPlantCd: "MMMM    ", productTypeCd: "A001" }, slab: {} },
              { order: { confirmedPlantCd: "        ", productTypeCd: "A001" }, slab: {} },
            ]
          : [],
        prefer_llm: preferLlm,
      });
      setPreview(result);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoadingPreview(false);
    }
  };

  const onSave = async () => {
    if (!preview) return;
    setSaving(true);
    setErr(null);
    try {
      const r = await saveTranspiled({
        step_id: preview.draft.step_id,
        function_name: preview.draft.function_name,
        python_source: preview.draft.python_source,
        overwrite: false,
      });
      setSavedPath(r.saved_path);
    } catch (e) {
      setErr(String(e));
    } finally {
      setSaving(false);
    }
  };

  const onSelectSample = (idx: number) => {
    const s = SAMPLE_JAVA_FILES[idx];
    setFilePath(s.path);
    setReferenceStep(s.referenceStep);
    setMethods([]);
    setPreview(null);
    setSavedPath(null);
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground flex items-center gap-2">
          <Wand2 size={20} className="text-primary" />
          Java → Python 자동 변환 (transpile)
          <HelpPopover
            title="Java → Python 자동 변환 — 무엇을 하는가"
            body={
              <>
                <p>
                  자바 메서드를 파이썬 step 함수로 자동 변환합니다. 두 단계로 동작:
                </p>
                <ol className="list-decimal list-inside text-xs space-y-0.5 my-1">
                  <li>tree-sitter 가 자바 메서드의 시그니처/본문/필드/import 추출</li>
                  <li>LLM 이 sandbox step 함수 (inputs: dict → outputs: dict) 작성</li>
                </ol>
                <p>
                  변환 후 <b>동치성 검증</b> — 기존 미러 step 이 있으면 같은 입력으로 두 결과를 비교 (shadow), 없으면 구조 검증 (signature / 금지 import).
                </p>
                <p className="text-[10px]">
                  목적: 다른 도메인의 자바 시스템 (예: 공정관리/SCM) 도 1시간 안에 시뮬레이션 단계로 편입.
                </p>
              </>
            }
          />
        </h1>
        <p className="text-xs text-muted-foreground mt-1">
          자바 메서드를 파이썬 step 으로 자동 변환 + 동치성 검증. 다른 도메인 적용 자동화의 핵심.
        </p>
      </div>

      {/* 1. 자바 파일 + 메서드 선택 */}
      <section className="rounded-lg border border-border bg-card p-4 space-y-3">
        <h2 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
          <Code2 size={14} className="text-primary" />
          1. 자바 파일 선택
        </h2>
        <div className="flex flex-wrap gap-2">
          {SAMPLE_JAVA_FILES.map((s, i) => (
            <button
              key={s.path}
              onClick={() => onSelectSample(i)}
              className={`text-xs rounded border px-2 py-1 transition-colors ${
                filePath === s.path
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border text-muted-foreground hover:bg-muted"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
        <div className="space-y-1">
          <label className="block text-[11px] font-medium text-foreground">자바 경로 (프로젝트 루트 기준)</label>
          <input
            type="text"
            value={filePath}
            onChange={(e) => setFilePath(e.target.value)}
            className="w-full rounded border border-border bg-background px-2 py-1.5 text-xs font-mono"
          />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="block text-[11px] font-medium text-foreground">참조 step ID (동치성 비교용)</label>
            <input
              type="text"
              value={referenceStep}
              onChange={(e) => setReferenceStep(e.target.value)}
              placeholder="thickness / slab_count / ..."
              className="w-full rounded border border-border bg-background px-2 py-1.5 text-xs font-mono"
            />
            <p className="text-[10px] text-muted-foreground">
              비우면 구조 검증만. 채우면 같은 입력으로 두 결과 shadow 비교.
            </p>
          </div>
          <div className="space-y-1">
            <label className="block text-[11px] font-medium text-foreground">목표 step_id (LLM 추천 override)</label>
            <input
              type="text"
              value={targetStepId}
              onChange={(e) => setTargetStepId(e.target.value)}
              placeholder="(LLM 자동 추천)"
              className="w-full rounded border border-border bg-background px-2 py-1.5 text-xs font-mono"
            />
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={onLoadMethods}
            disabled={loadingList}
            className="inline-flex items-center gap-1 rounded border border-border px-2.5 py-1.5 text-xs hover:bg-muted disabled:opacity-50"
          >
            {loadingList ? <Loader2 size={12} className="animate-spin" /> : <Code2 size={12} />}
            메서드 목록 불러오기
          </button>
          <label className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={preferLlm}
              onChange={(e) => setPreferLlm(e.target.checked)}
              className="accent-primary"
            />
            LLM 사용 (해제 시 fallback stub)
          </label>
        </div>

        {methods.length > 0 && (
          <div className="space-y-1.5">
            <label className="block text-[11px] font-medium text-foreground">메서드 ({methods.length}건)</label>
            <select
              value={methodName}
              onChange={(e) => {
                const m = methods.find((x) => x.method_name === e.target.value);
                setMethodName(e.target.value);
                if (m) setClassName(m.class_name);
              }}
              className="w-full rounded border border-border bg-background px-2 py-1.5 text-xs font-mono"
            >
              {methods.map((m) => (
                <option key={`${m.class_name}.${m.method_name}`} value={m.method_name}>
                  {m.class_name}.{m.method_name}({m.parameters.map(([t, n]) => `${t} ${n}`).join(", ")})
                  {" "}— L{m.signature_line}~{m.end_line}
                </option>
              ))}
            </select>
          </div>
        )}
      </section>

      {/* 2. 변환 + 검증 */}
      <section className="rounded-lg border border-border bg-card p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
            <Sparkles size={14} className="text-amber-500" />
            2. LLM 변환 + 동치성 검증
          </h2>
          <button
            onClick={onPreview}
            disabled={loadingPreview || !methodName}
            className="inline-flex items-center gap-1 rounded bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {loadingPreview ? <Loader2 size={12} className="animate-spin" /> : <Wand2 size={12} />}
            변환 미리보기
          </button>
        </div>

        {err && (
          <div className="rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {err}
          </div>
        )}

        {preview && (
          <div className="space-y-3">
            {/* 자바 요약 */}
            <div className="rounded border border-border bg-muted/30 p-2 text-[11px] space-y-0.5">
              <p>
                <span className="font-mono text-muted-foreground">{preview.java_summary.class_name}.{preview.java_summary.method_name}</span>
                {" "}— L{preview.java_summary.lines}
              </p>
              <p className="text-muted-foreground font-mono">{preview.java_summary.signature}</p>
              {preview.java_summary.javadoc && (
                <p className="text-muted-foreground italic">{preview.java_summary.javadoc.slice(0, 200)}</p>
              )}
            </div>

            {/* draft 메타 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
              <Badge label="step_id" value={preview.draft.step_id} />
              <Badge label="신뢰도" value={`${(preview.draft.confidence * 100).toFixed(0)}%`} />
              <Badge label="경로" value={preview.draft.method === "llm" ? "LLM" : "Fallback"} />
              <Badge label="검증 모드" value={preview.equivalence.mode === "shadow" ? "shadow 비교" : "구조 검증"} />
            </div>

            {/* rationale */}
            <div className="rounded border border-amber-500/30 bg-amber-500/5 p-2 text-[11px]">
              <p className="font-medium text-foreground mb-0.5">변환 근거</p>
              <p className="text-muted-foreground">{preview.draft.rationale}</p>
            </div>

            {/* equivalence */}
            <EquivalenceCard report={preview.equivalence} />

            {/* python source */}
            <div className="space-y-1">
              <p className="text-[11px] font-medium text-foreground">생성된 파이썬 코드</p>
              <pre className="rounded border border-border bg-muted/20 p-2 text-[11px] font-mono overflow-x-auto max-h-[400px]">
                {preview.draft.python_source}
              </pre>
            </div>

            {/* 저장 */}
            <div className="flex items-center gap-2">
              <button
                onClick={onSave}
                disabled={saving || !preview.equivalence.passed}
                title={
                  preview.equivalence.passed
                    ? "sandbox/steps_transpiled/<step_id>.py 로 저장"
                    : "동치성 검증 통과 후 저장 가능"
                }
                className="inline-flex items-center gap-1 rounded bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                {saving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                sandbox 에 저장
              </button>
              {savedPath && (
                <span className="inline-flex items-center gap-0.5 text-[11px] text-emerald-700 dark:text-emerald-300">
                  <CheckCircle2 size={12} /> {savedPath}
                </span>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function Badge({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-border bg-background px-2 py-1">
      <p className="text-[9px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="text-foreground font-mono truncate">{value}</p>
    </div>
  );
}

function EquivalenceCard({ report }: { report: PreviewResponse["equivalence"] }) {
  const tone = report.passed
    ? "border-emerald-500/30 bg-emerald-500/5"
    : "border-red-500/30 bg-red-500/5";
  const icon = report.passed ? (
    <CheckCircle2 size={14} className="text-emerald-600" />
  ) : (
    <XCircle size={14} className="text-red-600" />
  );
  return (
    <div className={`rounded border p-2 text-[11px] space-y-1 ${tone}`}>
      <div className="flex items-center gap-1.5">
        {icon}
        <p className="font-medium text-foreground">동치성 검증 — {report.summary}</p>
      </div>
      {report.mode === "shadow" && (
        <p className="text-muted-foreground">
          샘플 {report.sample_count}건 · 일치 {report.matched} · 불일치 {report.mismatched}
        </p>
      )}
      {report.structural_errors.length > 0 && (
        <ul className="text-red-700 dark:text-red-300 list-disc list-inside space-y-0.5">
          {report.structural_errors.map((e, i) => (
            <li key={i} className="font-mono text-[10px]">
              <AlertTriangle size={10} className="inline mr-1" />
              {e}
            </li>
          ))}
        </ul>
      )}
      {report.field_diffs.length > 0 && (
        <details className="text-muted-foreground">
          <summary className="cursor-pointer">대표 차이 ({report.field_diffs.length}건)</summary>
          <ul className="mt-1 space-y-0.5 font-mono text-[10px]">
            {report.field_diffs.slice(0, 10).map((d, i) => (
              <li key={i}>
                <span className="text-foreground">{d.path}</span>: {JSON.stringify(d.before)?.slice(0, 40)} → {JSON.stringify(d.after)?.slice(0, 40)}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
