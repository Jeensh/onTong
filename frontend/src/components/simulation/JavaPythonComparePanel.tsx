"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  ClipboardCopy,
  Database,
  GitCompare,
  Loader2,
  Play,
  RefreshCw,
  XCircle,
} from "lucide-react";
import {
  getDifferentialStatus,
  runDifferential,
  type DifferentialResult,
  type DifferentialStatus,
  type FieldDiff,
} from "@/lib/simulation/differentialApi";
import { JsonTable } from "./JsonTable";
import { OntologyEvidenceToggle } from "./OntologyEvidencePanel";

const SLAB_DESIGN_BASE = "http://localhost:8080";

// fetch 실패 시 fallback 정적 시나리오 (slab-design 미가동 케이스)
const FALLBACK_ORDERS: PresetOrder[] = [
  {
    id: "fb-normal",
    label: "정상 (fallback)",
    category: "정상",
    payload: {
      cmpCd: "K", orgCd: "K01", orderNo: "ORD-NORMAL-001",
      stockCode: 0, productTypeCd: "A001", confirmedPlantCd: "K K K   ",
      orderWidth: "1200", orderLength: "3000",
      pkgWgtLow: "5", pkgWgtHigh: "30",
      orderWgtLow: "8", orderWgtHigh: "25",
      gradeCd: "G01", customerCd: "C001",
    },
  },
  {
    id: "fb-dg001",
    label: "DG001 — 재고주문",
    category: "DG001",
    payload: {
      cmpCd: "K", orgCd: "K01", orderNo: "ORD-DG001",
      stockCode: 1, productTypeCd: "A001", confirmedPlantCd: "K K K   ",
      orderWidth: "1200", orderLength: "3000",
    },
  },
];

interface PresetOrder {
  id: string;
  label: string;            // dropdown 라벨 (사용자 가시)
  category: string;         // 정상 / 경계 / DG001 등
  payload: Record<string, unknown>;
}

interface OrderOsRow {
  cmpCd: string; orgCd: string; orderNo: string;
  osProgress?: string | null; closeFlag?: number | null; stockCode: number;
  designPendQty?: number; designPendQtyLow?: number; designPendQtyHigh?: number;
  confirmedPlantCd?: string; possiblePlantCd?: string;
  smDue?: string | null; hrDue?: string | null; hrfDue?: string | null;
  crDue?: string | null; anl1Due?: string | null; anl2Due?: string | null;
  galDue?: string | null; crfDue?: string | null;
}

interface OrderOmRow {
  cmpCd: string; orgCd: string; orderNo: string;
  orderWgtLow?: number; orderWgtHigh?: number;
  orderWidth?: number; orderLength?: number;
  designPendQty?: number; workDue?: string | null;
  pkgWgtLow?: number; pkgWgtHigh?: number;
  productTypeCd?: string; customerCd?: string;
  prodDue?: string | null; deliveryDue?: string | null;
}

interface OrderQdRow {
  cmpCd: string; orgCd: string; orderNo: string;
  gradeCd?: string;
  hrTgtWidth_1?: number | null; hrTgtWidth_2?: number | null;
  hrTgtWidth_3?: number | null; hrTgtWidth_4?: number | null;
  hrTgtWidth_5?: number | null;
}

/** ORDER_NO 가 'TC01-NORMAL    ' 처럼 우측 공백 패딩으로 옴 — 라벨용 trim, JSON엔 원본. */
function trimOrderNo(s: string): string {
  return s.replace(/\s+$/, "");
}

/** orderNo 의 카테고리 라벨 자동 분류 (TC04-ERR-DG001 → "DG001"). */
function categorizeFromOrderNo(orderNo: string): string {
  const trimmed = trimOrderNo(orderNo);
  const dgMatch = trimmed.match(/DG\d{3}/);
  if (dgMatch) return dgMatch[0];
  if (trimmed.includes("BOUNDARY")) return "경계";
  if (trimmed.includes("WIDE")) return "WIDE";
  if (trimmed.includes("NORMAL")) return "정상";
  return "기타";
}

const CATEGORY_TONE: Record<string, string> = {
  "정상": "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  "경계": "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  "WIDE": "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  "DG001": "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300",
  "DG002": "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300",
  "DG003": "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300",
  "DG004": "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300",
  "DG005": "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300",
  "DG101": "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300",
  "DG102": "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300",
  "기타": "border-border bg-muted/30 text-muted-foreground",
};

/** ORDER_OS + ORDER_OM + ORDER_QD merge → Differential `order` payload. */
function buildOrderPayload(os: OrderOsRow, om?: OrderOmRow, qd?: OrderQdRow): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    cmpCd: os.cmpCd, orgCd: os.orgCd, orderNo: os.orderNo,
    stockCode: os.stockCode,
    confirmedPlantCd: os.confirmedPlantCd,
  };
  if (os.designPendQty != null) payload.designPendQty = String(os.designPendQty);
  if (os.designPendQtyLow != null) payload.designPendQtyLow = String(os.designPendQtyLow);
  if (os.designPendQtyHigh != null) payload.designPendQtyHigh = String(os.designPendQtyHigh);
  if (os.smDue) payload.smDue = os.smDue;
  if (os.hrDue) payload.hrDue = os.hrDue;
  if (os.hrfDue) payload.hrfDue = os.hrfDue;
  if (om) {
    if (om.orderWidth != null) payload.orderWidth = String(om.orderWidth);
    if (om.orderLength != null) payload.orderLength = String(om.orderLength);
    if (om.orderWgtLow != null) payload.orderWgtLow = String(om.orderWgtLow);
    if (om.orderWgtHigh != null) payload.orderWgtHigh = String(om.orderWgtHigh);
    if (om.pkgWgtLow != null) payload.pkgWgtLow = String(om.pkgWgtLow);
    if (om.pkgWgtHigh != null) payload.pkgWgtHigh = String(om.pkgWgtHigh);
    if (om.workDue) payload.workDue = om.workDue;
    if (om.productTypeCd) payload.productTypeCd = om.productTypeCd;
    if (om.customerCd) payload.customerCd = om.customerCd;
  }
  if (qd) {
    if (qd.gradeCd) payload.gradeCd = qd.gradeCd;
    if (qd.hrTgtWidth_1 != null) payload.hrTgtWidth_1 = String(qd.hrTgtWidth_1);
    if (qd.hrTgtWidth_2 != null) payload.hrTgtWidth_2 = String(qd.hrTgtWidth_2);
    if (qd.hrTgtWidth_3 != null) payload.hrTgtWidth_3 = String(qd.hrTgtWidth_3);
  }
  return payload;
}

async function fetchPresets(): Promise<PresetOrder[]> {
  const [osRes, omRes, qdRes] = await Promise.all([
    fetch(`${SLAB_DESIGN_BASE}/api/sd/admin/orders/os`),
    fetch(`${SLAB_DESIGN_BASE}/api/sd/admin/orders/om`),
    fetch(`${SLAB_DESIGN_BASE}/api/sd/admin/orders/qd`),
  ]);
  if (!osRes.ok) throw new Error(`orders/os HTTP ${osRes.status}`);
  const osList: OrderOsRow[] = await osRes.json();
  const omList: OrderOmRow[] = omRes.ok ? await omRes.json() : [];
  const qdList: OrderQdRow[] = qdRes.ok ? await qdRes.json() : [];
  const omMap = new Map(omList.map((o) => [`${o.cmpCd}|${o.orgCd}|${o.orderNo}`, o]));
  const qdMap = new Map(qdList.map((o) => [`${o.cmpCd}|${o.orgCd}|${o.orderNo}`, o]));

  return osList.map((os) => {
    const key = `${os.cmpCd}|${os.orgCd}|${os.orderNo}`;
    const om = omMap.get(key);
    const qd = qdMap.get(key);
    const trimmed = trimOrderNo(os.orderNo);
    const cat = categorizeFromOrderNo(os.orderNo);
    return {
      id: trimmed,
      label: trimmed,
      category: cat,
      payload: buildOrderPayload(os, om, qd),
    };
  });
}

export function JavaPythonComparePanel() {
  const [status, setStatus] = useState<DifferentialStatus | null>(null);
  const [presets, setPresets] = useState<PresetOrder[]>(FALLBACK_ORDERS);
  const [presetsSource, setPresetsSource] = useState<"loading" | "h2" | "fallback">("loading");
  const [presetError, setPresetError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string>("");
  const [orderJson, setOrderJson] = useState(JSON.stringify(FALLBACK_ORDERS[0].payload, null, 2));
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<DifferentialResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    getDifferentialStatus().then(setStatus).catch(() => setStatus(null));
  }, []);

  const reloadPresets = async () => {
    setPresetsSource("loading");
    setPresetError(null);
    try {
      const list = await fetchPresets();
      if (list.length > 0) {
        setPresets(list);
        setPresetsSource("h2");
        setSelectedId(list[0].id);
        setOrderJson(JSON.stringify(list[0].payload, null, 2));
      } else {
        setPresets(FALLBACK_ORDERS);
        setPresetsSource("fallback");
        setPresetError("H2 에 시드 주문 0건");
      }
    } catch (e) {
      setPresets(FALLBACK_ORDERS);
      setPresetsSource("fallback");
      setPresetError(`slab-design (:8080) 미가용 — fallback 정적 샘플 사용 (${e instanceof Error ? e.message : String(e)})`);
    }
  };

  useEffect(() => {
    reloadPresets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onSelectPreset = (id: string) => {
    setSelectedId(id);
    const p = presets.find((x) => x.id === id);
    if (p) setOrderJson(JSON.stringify(p.payload, null, 2));
  };

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(orderJson);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      // ignore
    }
  };

  const onRun = async () => {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(orderJson);
    } catch {
      setError("order JSON 파싱 실패 — 형식 확인");
      return;
    }
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const r = await runDifferential({ order: parsed });
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  };

  // 카테고리별 그룹핑
  const grouped = useMemo(() => {
    const m = new Map<string, PresetOrder[]>();
    for (const p of presets) {
      if (!m.has(p.category)) m.set(p.category, []);
      m.get(p.category)!.push(p);
    }
    return m;
  }, [presets]);

  return (
    <div className="space-y-5">
      {/* ── 상태 ───────────────────────────────────────── */}
      <div className="rounded-lg border border-border bg-card p-4 space-y-2">
        <div className="flex items-center gap-2">
          <GitCompare size={18} className="text-primary" />
          <h2 className="text-base font-semibold">Java ↔ Python 결과 비교 (Differential)</h2>
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">
          같은 입력으로 Java <code>SdDesigner.design()</code> 와 Python <code>pipeline_full</code> 양쪽
          실행 → field-by-field 결과 차이. BigDecimal tolerance (rel 1e-9 / abs 1e-12) 적용.
        </p>
        <OntologyEvidenceToggle
          actionFqn="action.scm.슬랩설계_실행"
          label="📚 이 비교의 온톨로지 근거 (Java/Python 모두 같은 ontology Action 기반)"
        />
        {status ? (
          status.java_bridge_available ? (
            <p className="text-xs text-emerald-500 flex items-center gap-1.5">
              <CheckCircle2 size={12} /> Java Bridge 활성 — 양쪽 실행 가능
            </p>
          ) : (
            <p className="text-xs text-amber-500 flex items-start gap-1.5">
              <AlertCircle size={12} className="mt-0.5 flex-shrink-0" />
              <span>Java Bridge 미빌드 — Python 단독 실행만 가능. {status.guide}</span>
            </p>
          )
        ) : null}
      </div>

      {/* ── 입력 ───────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-lg border border-border bg-card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold flex items-center gap-1.5">
              <Database size={13} className="text-primary" />
              H2 시드 주문 — 유형별 프리셋
            </h3>
            <button
              onClick={reloadPresets}
              disabled={presetsSource === "loading"}
              className="text-[10px] text-muted-foreground hover:text-foreground inline-flex items-center gap-0.5"
              title="slab-design H2 에서 다시 불러오기"
            >
              {presetsSource === "loading" ? <Loader2 size={10} className="animate-spin" /> : <RefreshCw size={10} />}
              새로고침
            </button>
          </div>

          {presetError && (
            <div className="rounded border border-amber-500/30 bg-amber-500/5 px-2 py-1.5 text-[10px] text-amber-700 dark:text-amber-300">
              {presetError}
            </div>
          )}

          <div className="space-y-2">
            {Array.from(grouped.entries()).map(([cat, items]) => (
              <div key={cat}>
                <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1 flex items-center gap-1">
                  <span className={`inline-block rounded border px-1 py-0 ${CATEGORY_TONE[cat] ?? CATEGORY_TONE["기타"]}`}>
                    {cat}
                  </span>
                  <span>{items.length}건</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {items.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => onSelectPreset(p.id)}
                      className={`text-[11px] font-mono px-2 py-1 rounded border transition-colors ${
                        selectedId === p.id
                          ? "border-primary bg-primary/10 text-primary"
                          : "border-border bg-muted/30 hover:bg-muted text-foreground"
                      }`}
                      title={`${p.category} — ${p.label}`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between pt-1">
            <h3 className="text-sm font-semibold">Order JSON</h3>
            <button
              onClick={onCopy}
              className="text-[10px] text-muted-foreground hover:text-foreground inline-flex items-center gap-0.5"
              title="현재 JSON 클립보드 복사"
            >
              <ClipboardCopy size={10} />
              {copied ? "복사됨!" : "복사"}
            </button>
          </div>
          <textarea
            value={orderJson}
            onChange={(e) => setOrderJson(e.target.value)}
            className="w-full h-64 text-xs font-mono p-2.5 rounded border border-border bg-muted/30 focus:outline-none focus:ring-1 focus:ring-primary"
            spellCheck={false}
          />
          <button
            onClick={onRun}
            disabled={running}
            className="text-xs px-3 py-2 rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 inline-flex items-center gap-1.5"
          >
            {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            양쪽 실행 + 비교
          </button>
        </div>

        {/* ── 결과 ─────────────────────────────────────── */}
        <div className="rounded-lg border border-border bg-card p-4 space-y-3 min-h-[400px]">
          <h3 className="text-sm font-semibold">결과</h3>
          {error ? (
            <div className="text-xs text-red-500 flex items-start gap-2">
              <XCircle size={14} className="mt-0.5" />
              {error}
            </div>
          ) : null}

          {!result && !error && !running ? (
            <p className="text-xs text-muted-foreground">「양쪽 실행 + 비교」 버튼을 눌러 시작하세요.</p>
          ) : null}

          {result ? <ResultView r={result} /> : null}
        </div>
      </div>
    </div>
  );
}

function ResultView({ r }: { r: DifferentialResult }) {
  const allMatch = r.java_ok && r.python_ok && r.mismatched_count === 0;

  return (
    <div className="space-y-3 text-xs">
      <div className="grid grid-cols-2 gap-2">
        <StatusBadge label="Java" ok={r.java_ok} elapsed={r.java_elapsed_sec} avail={r.java_available} />
        <StatusBadge label="Python" ok={r.python_ok} elapsed={r.python_elapsed_sec} />
      </div>

      {r.java_ok && r.python_ok ? (
        <div className={`rounded p-2.5 border ${allMatch ? "bg-emerald-500/5 border-emerald-500/30" : "bg-red-500/5 border-red-500/30"}`}>
          <p className="font-semibold flex items-center gap-1.5">
            {allMatch ? (
              <><CheckCircle2 size={14} className="text-emerald-500" /> 일치: {r.matched_count}건 / 차이: 0건</>
            ) : (
              <><XCircle size={14} className="text-red-500" /> 일치 {r.matched_count} · 차이 {r.mismatched_count}</>
            )}
          </p>
        </div>
      ) : null}

      {r.field_diffs.length > 0 ? (
        <div className="rounded border border-border overflow-hidden">
          <table className="w-full text-xs font-mono">
            <thead className="bg-muted/40">
              <tr>
                <th className="text-left px-2 py-1">경로</th>
                <th className="text-left px-2 py-1 text-amber-500">Java</th>
                <th className="text-left px-2 py-1 text-primary">Python</th>
              </tr>
            </thead>
            <tbody>
              {r.field_diffs.slice(0, 20).map((d: FieldDiff) => (
                <tr key={d.path} className="border-t border-border">
                  <td className="px-2 py-1">{d.path}</td>
                  <td className="px-2 py-1 text-amber-500">{stringify(d.java)}</td>
                  <td className="px-2 py-1 text-primary">{stringify(d.python)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {r.field_diffs.length > 20 ? (
            <p className="text-[10px] text-muted-foreground p-1.5 bg-muted/20">
              + {r.field_diffs.length - 20}건 더 있음
            </p>
          ) : null}
        </div>
      ) : null}

      {r.java_error ? (
        <details className="text-xs">
          <summary className="cursor-pointer text-amber-500">Java 에러 상세</summary>
          <pre className="mt-1 p-2 bg-muted/30 rounded text-[10px] whitespace-pre-wrap">{r.java_error}</pre>
        </details>
      ) : null}

      {r.java_ok && r.java_payload ? (
        <details className="text-xs">
          <summary className="cursor-pointer">Java 응답 raw</summary>
          <div className="mt-1.5">
            <JsonTable data={r.java_payload} />
          </div>
        </details>
      ) : null}

      {r.python_ok && r.python_payload ? (
        <details className="text-xs">
          <summary className="cursor-pointer">Python 응답 raw</summary>
          <div className="mt-1.5">
            <JsonTable data={r.python_payload} />
          </div>
        </details>
      ) : null}
    </div>
  );
}

function StatusBadge({ label, ok, elapsed, avail }: { label: string; ok: boolean; elapsed: number; avail?: boolean }) {
  if (avail === false) {
    return (
      <div className="rounded border border-amber-500/30 bg-amber-500/5 p-2 text-xs">
        <span className="font-semibold">{label}</span>: <span className="text-amber-500">미가용</span>
      </div>
    );
  }
  return (
    <div className={`rounded border p-2 text-xs ${ok ? "border-emerald-500/30 bg-emerald-500/5" : "border-red-500/30 bg-red-500/5"}`}>
      <span className="font-semibold">{label}</span>:{" "}
      <span className={ok ? "text-emerald-500" : "text-red-500"}>
        {ok ? "OK" : "FAIL"}
      </span>
      <span className="text-muted-foreground ml-1.5">({(elapsed * 1000).toFixed(0)}ms)</span>
    </div>
  );
}

function stringify(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}
