"use client";

import { Cpu, GitBranch, Network, Search } from "lucide-react";

export function ModelingSection() {
  return (
    <div className="flex h-full">
      {/* Left: Navigation */}
      <div className="w-64 border-r flex flex-col">
        <div className="p-3 border-b">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <Cpu className="w-4 h-4" />
            Source-Domain Modeling
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            코드 ↔ 도메인 매핑 관리
          </p>
        </div>
        <div className="flex-1 overflow-auto p-2">
          <div className="space-y-1">
            {[
              { icon: <Search className="w-3.5 h-3.5" />, label: "코드 분석", desc: "tree-sitter 파싱" },
              { icon: <Network className="w-3.5 h-3.5" />, label: "온톨로지 그래프", desc: "SCOR + ISA-95" },
              { icon: <GitBranch className="w-3.5 h-3.5" />, label: "매핑 관리", desc: "코드 ↔ 도메인" },
            ].map((item) => (
              <button
                key={item.label}
                className="w-full text-left p-2.5 rounded-lg hover:bg-muted transition-colors flex items-start gap-2"
              >
                <span className="mt-0.5 text-muted-foreground">{item.icon}</span>
                <div>
                  <div className="text-sm font-medium">{item.label}</div>
                  <div className="text-xs text-muted-foreground">{item.desc}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Center: Main workspace */}
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center max-w-md">
          <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mx-auto mb-4">
            <Cpu className="w-8 h-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-medium">Modeling Workspace</h3>
          <p className="text-sm text-muted-foreground mt-2">
            코드 분석, 온톨로지 관리, 영향도 분석을 수행하는 IT 담당자용 섹션입니다.
          </p>
          <div className="mt-6 grid grid-cols-2 gap-3">
            {[
              { label: "코드 파싱", status: "Phase 1", color: "bg-blue-100 text-blue-700" },
              { label: "온톨로지 적재", status: "Phase 1", color: "bg-blue-100 text-blue-700" },
              { label: "매핑 엔진", status: "Phase 1", color: "bg-blue-100 text-blue-700" },
              { label: "영향 분석", status: "Phase 1", color: "bg-blue-100 text-blue-700" },
              { label: "시뮬레이션 실행", status: "Phase 2", color: "bg-amber-100 text-amber-700" },
              { label: "데이터 연동", status: "Phase 3", color: "bg-gray-100 text-gray-600" },
            ].map((item) => (
              <div key={item.label} className="p-3 rounded-lg bg-muted/50 text-left">
                <div className="text-sm font-medium">{item.label}</div>
                <span className={`text-[10px] px-1.5 py-0.5 rounded ${item.color} mt-1 inline-block`}>
                  {item.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right: Agent placeholder */}
      <div className="w-80 border-l flex flex-col">
        <div className="p-3 border-b">
          <h3 className="text-sm font-semibold">ModelingCopilot</h3>
          <p className="text-xs text-muted-foreground">코드 분석 AI 어시스턴트</p>
        </div>
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="text-center text-muted-foreground">
            <p className="text-sm">AI 어시스턴트가 여기에 표시됩니다</p>
            <p className="text-xs mt-1">
              코드 영향 분석, 매핑 리뷰, 온톨로지 질의 등
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
