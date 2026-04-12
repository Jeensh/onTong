"use client";

import React, { useState } from "react";
import { Code, Network, GitCompare, Search, CheckSquare } from "lucide-react";
import { CodeGraphViewer } from "./modeling/CodeGraphViewer";
import { DomainOntologyEditor } from "./modeling/DomainOntologyEditor";
import { MappingSplitView } from "./modeling/MappingSplitView";
import { ImpactQueryPanel } from "./modeling/ImpactQueryPanel";
import { ApprovalList } from "./modeling/ApprovalList";

type ModelingView = "code" | "ontology" | "mapping" | "impact" | "approval";

interface NavItem {
  id: ModelingView;
  label: string;
  icon: React.ReactNode;
  description: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: "code", label: "코드 분석", icon: <Code size={18} />, description: "Java 코드 파싱 및 의존성 그래프" },
  { id: "ontology", label: "도메인 온톨로지", icon: <Network size={18} />, description: "SCOR+ISA-95 프로세스 트리" },
  { id: "mapping", label: "매핑 관리", icon: <GitCompare size={18} />, description: "코드 ↔ 도메인 연결" },
  { id: "impact", label: "영향분석", icon: <Search size={18} />, description: "변경 시 영향 범위 조회" },
  { id: "approval", label: "검토 요청", icon: <CheckSquare size={18} />, description: "매핑 승인/반려 관리" },
];

export function ModelingSection() {
  const [activeView, setActiveView] = useState<ModelingView>("mapping");
  const [repoId, setRepoId] = useState<string>("");

  return (
    <div className="flex h-full">
      {/* Left nav */}
      <div className="w-56 border-r border-border bg-muted/30 p-3 flex flex-col gap-1">
        <div className="px-2 py-3 mb-2">
          <h2 className="text-sm font-semibold text-foreground">Modeling</h2>
          <p className="text-xs text-muted-foreground mt-1">Section 2</p>
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

        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveView(item.id)}
            className={`flex items-center gap-2 px-3 py-2 rounded text-sm transition-colors ${
              activeView === item.id
                ? "bg-primary/10 text-primary font-medium"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            }`}
          >
            {item.icon}
            {item.label}
          </button>
        ))}
      </div>

      {/* Main content */}
      <div className="flex-1 p-6 overflow-auto">
        {!repoId ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <p>Repository ID를 입력하세요</p>
          </div>
        ) : (
          <ViewRouter view={activeView} repoId={repoId} />
        )}
      </div>
    </div>
  );
}

function ViewRouter({ view, repoId }: { view: ModelingView; repoId: string }) {
  switch (view) {
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
  }
}
