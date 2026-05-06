"use client";

import { useEffect } from "react";
import { useWorkbench } from "./store";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";
import { OntologyGraph } from "./OntologyGraph";

/**
 * Graph mode (V7 IA, D plan).
 * 옛 L1/L2/L4/L5 mock view 제거 — xyflow + ELK Layered (R4-T1.3 결정) 기반 실 데이터 그래프 하나로 단순화.
 * (L5 anchor micro-graph 는 우리 차별 포인트라 별도 phase 에서 부활)
 *
 * Esc 로 닫기. 키보드 단축키는 OntologyGraph 내부 검색박스/슬라이더 가 처리.
 */
export function GraphMode() {
  const { setGraphMode, activeRepoId } = useWorkbench();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tgt = e.target as HTMLElement | null;
      if (tgt && (tgt.tagName === "INPUT" || tgt.tagName === "TEXTAREA" || tgt.isContentEditable)) {
        return;
      }
      if (e.key === "Escape") setGraphMode(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setGraphMode]);

  return (
    <div className="flex flex-col h-full">
      <header className="h-9 px-3 bg-card border-b border-border flex items-center gap-3">
        <h3 className="text-[12px] font-semibold flex items-center gap-1.5">
          <span>🌐</span> 온톨로지 그래프
        </h3>
        <span className="text-[10px] text-muted-foreground">
          검색 → focus · 모드 / 노드 수 슬라이더는 그래프 위 toolbar 에서 조절
        </span>
        <div className="ml-auto">
          <Button variant="outline" size="sm" onClick={() => setGraphMode(false)} className="gap-1 h-7">
            <X className="w-3 h-3" /> 닫기 (esc)
          </Button>
        </div>
      </header>
      <div className="flex-1 relative">
        <OntologyGraph repoId={activeRepoId} />
      </div>
    </div>
  );
}
