// frontend/src/components/sections/ModelingSection.tsx
"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  Code,
  Network,
  GitBranch,
  GitCompare,
  Search,
  CheckSquare,
  PackageOpen,
  Loader2,
  CircleCheck,
  Circle,
  CircleDot,
  Zap,
  Settings2,
} from "lucide-react";
import { CodeGraphViewer } from "./modeling/CodeGraphViewer";
import { DomainOntologyEditor } from "./modeling/DomainOntologyEditor";
import { MappingSplitView } from "./modeling/MappingSplitView";
import { ImpactQueryPanel } from "./modeling/ImpactQueryPanel";
import { ApprovalList } from "./modeling/ApprovalList";
import { AnalysisConsole } from "./modeling/AnalysisConsole";
import { SimulationPanel } from "./modeling/SimulationPanel";
import { MappingWorkbench } from "./modeling/MappingWorkbench";
import { seedScmDemo, getCodeGraph, getOntologyTree, getMappings } from "@/lib/api/modeling";

type ModelingView = "analysis" | "simulation" | "workbench" | "code" | "ontology" | "mapping" | "impact" | "approval";

interface NavItem {
  id: ModelingView;
  label: string;
  icon: React.ReactNode;
  description: string;
  step?: number;
}

const MAIN_NAV: NavItem[] = [
  { id: "analysis", label: "분석 콘솔", icon: <Search size={18} />, description: "자연어 영향 분석" },
  { id: "simulation", label: "시뮬레이션", icon: <Zap size={18} />, description: "파라미터 what-if 분석" },
  { id: "workbench", label: "매핑 워크벤치", icon: <GitBranch size={18} />, description: "코드-도메인 시각 매핑" },
];

const SETTINGS_NAV: NavItem[] = [
  { id: "code", label: "코드 분석", icon: <Code size={18} />, description: "Java 코드 파싱", step: 1 },
  { id: "ontology", label: "도메인 온톨로지", icon: <Network size={18} />, description: "SCOR+ISA-95 트리", step: 2 },
  { id: "mapping", label: "매핑 관리", icon: <GitCompare size={18} />, description: "코드 ↔ 도메인 연결", step: 3 },
  { id: "approval", label: "검토 요청", icon: <CheckSquare size={18} />, description: "매핑 승인/반려" },
];

interface WorkflowStatus {
  codeParsed: boolean;
  ontologyLoaded: boolean;
  mappingExists: boolean;
}

export function ModelingSection() {
  const [activeView, setActiveView] = useState<ModelingView>("analysis");
  const [repoId, setRepoId] = useState<string>("");
  const [seeding, setSeeding] = useState(false);
  const [seedResult, setSeedResult] = useState<string | null>(null);
  const [workflow, setWorkflow] = useState<WorkflowStatus>({ codeParsed: false, ontologyLoaded: false, mappingExists: false });
  const [simTarget, setSimTarget] = useState<string | null>(null);

  const checkWorkflow = useCallback(async (rid: string) => {
    if (!rid) return;
    const status: WorkflowStatus = { codeParsed: false, ontologyLoaded: false, mappingExists: false };
    try {
      const [codeRes, ontoRes, mapRes] = await Promise.allSettled([
        getCodeGraph(rid),
        getOntologyTree(),
        getMappings(rid),
      ]);
      if (codeRes.status === "fulfilled" && codeRes.value.entities.length > 0) status.codeParsed = true;
      if (ontoRes.status === "fulfilled" && ontoRes.value.nodes.length > 0) status.ontologyLoaded = true;
      if (mapRes.status === "fulfilled" && mapRes.value.mappings.length > 0) status.mappingExists = true;
    } catch { /* ignore */ }
    setWorkflow(status);
  }, []);

  useEffect(() => {
    if (repoId) checkWorkflow(repoId);
  }, [repoId, checkWorkflow]);

  useEffect(() => {
    if (repoId) checkWorkflow(repoId);
  }, [activeView, repoId, checkWorkflow]);

  const handleLoadDemo = async () => {
    setSeeding(true);
    setSeedResult(null);
    try {
      const result = await seedScmDemo();
      setRepoId("scm-demo");
      setSeedResult(
        `${result.files_parsed}개 파일, ${result.entities_count}개 엔티티, ${result.mappings_created}개 매핑 로드 완료`
      );
      // Auto-navigate to analysis console after demo load
      setActiveView("analysis");
    } catch (e) {
      setSeedResult(`오류: ${(e as Error).message}`);
    } finally {
      setSeeding(false);
    }
  };

  const handleNavigateToSim = (entityId: string) => {
    setSimTarget(entityId);
    setActiveView("simulation");
  };

  const nextStep = !workflow.codeParsed ? 1 : !workflow.ontologyLoaded ? 2 : !workflow.mappingExists ? 3 : 0;

  function getStepIcon(item: NavItem) {
    if (!item.step || !repoId) return null;
    const done =
      (item.step === 1 && workflow.codeParsed) ||
      (item.step === 2 && workflow.ontologyLoaded) ||
      (item.step === 3 && workflow.mappingExists);
    const isNext = item.step === nextStep;

    if (done) return <CircleCheck className="h-3.5 w-3.5 text-green-500 shrink-0" />;
    if (isNext) return <CircleDot className="h-3.5 w-3.5 text-primary shrink-0 animate-pulse" />;
    return <Circle className="h-3.5 w-3.5 text-muted-foreground/40 shrink-0" />;
  }

  function renderNavButton(item: NavItem) {
    const stepIcon = getStepIcon(item);
    return (
      <button
        key={item.id}
        onClick={() => setActiveView(item.id)}
        className={`flex items-center gap-2 px-3 py-2 rounded text-sm transition-colors ${
          activeView === item.id
            ? "bg-primary/10 text-primary font-medium"
            : item.step === nextStep && repoId
            ? "text-foreground bg-muted/50 hover:bg-muted"
            : "text-muted-foreground hover:bg-muted hover:text-foreground"
        }`}
      >
        {item.icon}
        <span className="flex-1 text-left">{item.label}</span>
        {stepIcon}
      </button>
    );
  }

  return (
    <div className="flex h-full">
      {/* Left nav */}
      <div className="w-56 border-r border-border bg-muted/30 p-3 flex flex-col gap-1">
        <div className="px-2 py-3 mb-2">
          <h2 className="text-sm font-semibold text-foreground">모델링</h2>
          <p className="text-xs text-muted-foreground mt-1">코드-도메인 연결 관리</p>
        </div>

        {/* Repo selector */}
        <div className="px-2 mb-3">
          <label className="text-xs text-muted-foreground">Repository</label>
          <input
            type="text"
            value={repoId}
            onChange={(e) => setRepoId(e.target.value)}
            placeholder="repo-id"
            className="w-full mt-1 px-2 py-1 text-xs bg-background border border-border rounded"
          />
        </div>

        {/* Main nav (analysis + simulation) */}
        {MAIN_NAV.map(renderNavButton)}

        {/* Divider */}
        <div className="flex items-center gap-2 px-3 py-2 mt-2">
          <Settings2 className="h-3 w-3 text-muted-foreground/60" />
          <span className="text-[10px] font-medium text-muted-foreground/60 uppercase tracking-wider">설정</span>
          <div className="flex-1 h-px bg-border" />
        </div>

        {/* Settings nav (code, ontology, mapping, approval) */}
        {SETTINGS_NAV.map(renderNavButton)}

        {/* Workflow hint */}
        {repoId && nextStep > 0 && (
          <div className="mt-3 mx-2 px-2 py-2 rounded bg-primary/5 border border-primary/20">
            <p className="text-[10px] text-primary font-medium">
              {nextStep === 1 && "코드를 파싱하세요"}
              {nextStep === 2 && "온톨로지를 로드하세요"}
              {nextStep === 3 && "코드-도메인 매핑을 추가하세요"}
            </p>
          </div>
        )}
        {repoId && nextStep === 0 && (
          <div className="mt-3 mx-2 px-2 py-2 rounded bg-green-500/5 border border-green-500/20">
            <p className="text-[10px] text-green-600 dark:text-green-400 font-medium">
              기본 설정 완료 — 분석 콘솔을 사용하세요
            </p>
          </div>
        )}
      </div>

      {/* Main content */}
      <div className="flex-1 p-6 overflow-auto">
        {!repoId ? (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-4">
            <PackageOpen className="h-12 w-12 opacity-20" />
            <div className="text-center space-y-2">
              <p className="text-sm font-medium text-foreground">Repository를 선택하세요</p>
              <p className="text-xs">왼쪽에서 Repository ID를 입력하거나, 데모 데이터를 로드하세요.</p>
            </div>
            <button
              onClick={handleLoadDemo}
              disabled={seeding}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {seeding ? <Loader2 className="h-4 w-4 animate-spin" /> : <PackageOpen className="h-4 w-4" />}
              SCM 데모 프로젝트 로드
            </button>
            {seedResult && (
              <p className={`text-xs ${seedResult.startsWith("오류") ? "text-red-500" : "text-green-600"}`}>
                {seedResult}
              </p>
            )}
          </div>
        ) : (
          <ViewRouter
            view={activeView}
            repoId={repoId}
            simTarget={simTarget}
            onNavigateToSim={handleNavigateToSim}
          />
        )}
      </div>
    </div>
  );
}

function ViewRouter({
  view,
  repoId,
  simTarget,
  onNavigateToSim,
}: {
  view: ModelingView;
  repoId: string;
  simTarget: string | null;
  onNavigateToSim: (entityId: string) => void;
}) {
  switch (view) {
    case "analysis":
      return <AnalysisConsole repoId={repoId} onNavigateToSim={onNavigateToSim} />;
    case "simulation":
      return <SimulationPanel repoId={repoId} initialEntityId={simTarget} />;
    case "code":
      return <CodeGraphViewer repoId={repoId} />;
    case "ontology":
      return <DomainOntologyEditor repoId={repoId} />;
    case "mapping":
      return <MappingSplitView repoId={repoId} />;
    case "impact":
      return <ImpactQueryPanel repoId={repoId} />;
    case "approval":
      return <ApprovalList repoId={repoId} />;
    case "workbench":
      return <MappingWorkbench repoId={repoId} />;
  }
}
