"use client";

import { useEffect, useMemo, useState } from "react";
import {
  BookMarked,
  Download,
  FileDown,
  FileUp,
  Loader2,
  Play,
  RefreshCw,
  Tag,
  Trash2,
} from "lucide-react";
import {
  deleteScenario,
  exportScenariosYaml,
  importScenariosYaml,
  listScenarios,
  seedScenarios,
  submitScenarioJob,
  type Scenario,
} from "@/lib/simulation/storageApi";
import { getStepLabel } from "@/lib/simulation/stepLabels";
import { HelpPopover } from "./HelpPopover";

export function ScenarioLibraryPanel() {
  const [items, setItems] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [tagFilter, setTagFilter] = useState<string>("");
  const [stepFilter, setStepFilter] = useState<string>("");
  const [running, setRunning] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [importYaml, setImportYaml] = useState("");
  const [importMsg, setImportMsg] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    setErr(null);
    try {
      const items = await listScenarios({
        tag: tagFilter || undefined,
        stepId: stepFilter || undefined,
      });
      setItems(items);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tagFilter, stepFilter]);

  const allTags = useMemo(() => {
    const set = new Set<string>();
    items.forEach((s) => s.tags.forEach((t) => set.add(t)));
    return Array.from(set).sort();
  }, [items]);

  const allSteps = useMemo(() => {
    const set = new Set<string>();
    items.forEach((s) => set.add(s.step_id));
    return Array.from(set).sort();
  }, [items]);

  const onSeed = async () => {
    setLoading(true);
    try {
      await seedScenarios();
      await refresh();
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  const onRun = async (scn: Scenario) => {
    setRunning(scn.id);
    try {
      const job = await submitScenarioJob(scn.id);
      // 잡 ID 만 알림 — 상세는 RunHistory 패널에서
      alert(`잡 큐 등록됨: ${job.id}\n결과는 '실행 이력' 패널에서 확인.`);
    } catch (e) {
      setErr(String(e));
    } finally {
      setRunning(null);
    }
  };

  const onDelete = async (id: string) => {
    if (!confirm("이 시나리오를 삭제하시겠습니까?")) return;
    await deleteScenario(id);
    await refresh();
  };

  const onExport = async () => {
    const text = await exportScenariosYaml({
      stepId: stepFilter || undefined,
      tag: tagFilter || undefined,
    });
    const blob = new Blob([text], { type: "text/yaml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `scenarios_${Date.now()}.yaml`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const onImport = async () => {
    if (!importYaml.trim()) return;
    setImportMsg(null);
    try {
      const r = await importScenariosYaml(importYaml, true);
      setImportMsg(`✓ imported=${r.imported}, skipped=${r.skipped}`);
      await refresh();
      if (r.imported > 0) {
        setImportYaml("");
        setTimeout(() => setImportOpen(false), 1500);
      }
    } catch (e) {
      setImportMsg(`✗ ${e}`);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground flex items-center gap-2">
          <BookMarked size={20} className="text-primary" />
          시나리오 라이브러리
          <HelpPopover
            title="시나리오 라이브러리 — 무엇을 하는가"
            body={
              <>
                <p>운영자가 검증할 만한 <b>룰 1줄 변경 카탈로그</b>. 한 시나리오 = step_id + inputs(YAML) + tags.</p>
                <p>"실행" 버튼 = AsyncJobQueue 등록 → Python 샌드박스에서 실제 실행 + 영구 저장. <b>scenario 가 baseline 을 가지면 자동 회귀 검증</b> 동시 실행.</p>
                <p>처음이면 <b>"YAML 시드 로드"</b> 클릭. 8건 (HR 실수율 0.92 / EDGING * 누락 / PlantMapping 마이그 등) 자동 등록.</p>
              </>
            }
          />
        </h1>
        <p className="text-xs text-muted-foreground mt-1">
          룰 변경 / 정합성 / 마이그레이션 시뮬을 한 곳에서 관리. YAML 시드 + 사용자 정의.
        </p>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={refresh}
          disabled={loading}
          className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-xs hover:bg-muted disabled:opacity-50"
        >
          {loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
          새로고침
        </button>
        <button
          onClick={onSeed}
          className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-xs hover:bg-muted"
        >
          <Download size={12} /> YAML 시드 로드
        </button>
        <button
          onClick={onExport}
          className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-xs hover:bg-muted"
          title="현재 필터 결과를 YAML 로 내보내기"
        >
          <FileDown size={12} /> Export
        </button>
        <button
          onClick={() => setImportOpen((v) => !v)}
          className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-xs hover:bg-muted"
          title="YAML 텍스트로 시나리오 일괄 등록"
        >
          <FileUp size={12} /> Import
        </button>

        <select
          value={tagFilter}
          onChange={(e) => setTagFilter(e.target.value)}
          className="rounded border border-border bg-background px-2 py-1 text-xs"
        >
          <option value="">모든 태그</option>
          {allTags.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>

        <select
          value={stepFilter}
          onChange={(e) => setStepFilter(e.target.value)}
          className="rounded border border-border bg-background px-2 py-1 text-xs"
        >
          <option value="">모든 step</option>
          {allSteps.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>

        <span className="text-xs text-muted-foreground ml-auto">{items.length} 건</span>
      </div>

      {err && (
        <div className="rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {err}
        </div>
      )}

      {importOpen && (
        <div className="rounded-lg border border-border bg-card p-3 space-y-2">
          <p className="text-xs font-medium text-foreground">
            YAML 시나리오 import (이전 export 파일 또는 직접 작성한 카탈로그)
          </p>
          <textarea
            value={importYaml}
            onChange={(e) => setImportYaml(e.target.value)}
            placeholder={`- id: scn-my-test\n  name: "테스트 시나리오"\n  step_id: thickness\n  inputs: {}\n  tags: [test]\n`}
            rows={8}
            className="w-full rounded border border-border bg-background px-2 py-1.5 text-[11px] font-mono"
          />
          <div className="flex items-center gap-2">
            <button
              onClick={onImport}
              disabled={!importYaml.trim()}
              className="inline-flex items-center gap-1 rounded bg-primary text-primary-foreground px-2 py-1 text-xs font-medium disabled:opacity-50"
            >
              <FileUp size={12} /> 등록
            </button>
            <button
              onClick={() => { setImportOpen(false); setImportMsg(null); }}
              className="rounded border border-border px-2 py-1 text-xs text-muted-foreground hover:bg-muted"
            >
              취소
            </button>
            {importMsg && (
              <span className={`text-xs ${importMsg.startsWith("✓") ? "text-emerald-600" : "text-destructive"}`}>
                {importMsg}
              </span>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {items.map((s) => (
          <div
            key={s.id}
            className="rounded-lg border border-border bg-card p-3 space-y-2 hover:border-primary/30 transition-colors"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-semibold text-foreground truncate">{s.name}</h3>
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  <span className="text-foreground">{getStepLabel(s.step_id)}</span>
                  <span className="font-mono text-muted-foreground/60"> · {s.step_id}</span>
                  <span className="font-mono text-muted-foreground/60"> · {s.source}</span>
                </p>
              </div>
              <div className="flex gap-1 flex-shrink-0">
                <button
                  onClick={() => onRun(s)}
                  disabled={running === s.id}
                  className="inline-flex items-center gap-1 rounded bg-primary text-primary-foreground px-2 py-1 text-xs font-medium disabled:opacity-50"
                  title="잡 큐에 등록 후 실행"
                >
                  {running === s.id ? (
                    <Loader2 size={11} className="animate-spin" />
                  ) : (
                    <Play size={11} />
                  )}
                  실행
                </button>
                {s.source !== "yaml" && (
                  <button
                    onClick={() => onDelete(s.id)}
                    className="inline-flex items-center gap-1 rounded border border-destructive/30 text-destructive px-2 py-1 text-xs hover:bg-destructive/10"
                  >
                    <Trash2 size={11} />
                  </button>
                )}
              </div>
            </div>
            {s.description && (
              <p className="text-xs text-muted-foreground">{s.description}</p>
            )}
            {s.tags.length > 0 && (
              <div className="flex flex-wrap gap-1 pt-1">
                {s.tags.map((t) => (
                  <span
                    key={t}
                    className="inline-flex items-center gap-0.5 rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground"
                  >
                    <Tag size={9} /> {t}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {items.length === 0 && !loading && (
        <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          등록된 시나리오가 없습니다. <button onClick={onSeed} className="text-primary underline">YAML 시드 로드</button> 를 눌러 기본 시나리오를 가져오세요.
        </div>
      )}
    </div>
  );
}
