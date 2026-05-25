"use client";

import { useEffect } from "react";
import { useWorkbench } from "./store";
import { TopBar } from "./TopBar";
import { LeftPanel } from "./LeftPanel";
import { MainPanel } from "./MainPanel";
import { RightPanel } from "./RightPanel";
import { GraphMode } from "./GraphMode";
import { StatusBar } from "./StatusBar";
import { CmdKPalette } from "./CmdKPalette";

/**
 * Workbench 통합 화면 (V7 IA, D plan).
 * - 좌측 navigator (모듈 트리 / 큐) + 메인 detail + 우측 컨텍스트 패널 의 3-pane.
 * - TabBar 제거 — 한 번에 한 노드 집중. breadcrumb 은 TopBar 가 노출.
 * - Graph mode 진입 시 좌측 navigator 는 그대로 유지 (필터링도 아직 graph 안에서 처리).
 */
export function WorkbenchShell() {
  const { graphModeActive, rightWidth, mainMode, setGraphMode, toggleCmdK } = useWorkbench();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        // 좌측 검색 input 에 입력 중이었으면 그 텍스트를 ⌘K 로 이어받음 — 페르소나 P3 의
        // focus 충돌 해소. textarea 는 제외 (긴 글 작성 중 우발적 트리거 방지).
        const ae = document.activeElement;
        let initial = "";
        if (ae && ae.tagName === "INPUT") {
          const v = (ae as HTMLInputElement).value;
          if (v && v.trim().length > 0) initial = v.trim();
        }
        toggleCmdK(undefined, initial);
      }
      if (e.key === "Escape") {
        toggleCmdK(false);
        if (useWorkbench.getState().graphModeActive) setGraphMode(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggleCmdK, setGraphMode]);

  // R2-W2-Now / X2 (정정): Authoring 모드의 입력 source 는 좌측 코드 트리이므로
  // LeftPanel 은 유지. 사용자가 불편하다고 한 것은 우측의 "📄 코드 / 📖 매뉴얼
  // / 📞 호출지점 / 🌊 영향" 4-tab 패널 (RightPanel) — 이건 Authoring 모드에서
  // 컨텍스트상 불필요하므로 숨김.
  const authoringMode = mainMode === "authoring" && !graphModeActive;

  const gridTemplate = authoringMode
    ? { columns: "280px 1fr", areas: `"top top" "left main" "status status"` }
    : graphModeActive
    ? { columns: "260px 1fr", areas: `"top top" "left main" "status status"` }
    : {
        columns: `280px minmax(420px, 1fr) ${rightWidth}px`,
        areas: `"top top top" "left main right" "status status status"`,
      };

  return (
    <div
      className="grid h-full bg-background text-foreground"
      style={{
        gridTemplateRows: "36px 1fr 24px",
        gridTemplateColumns: gridTemplate.columns,
        gridTemplateAreas: gridTemplate.areas,
      }}
    >
      <TopBar />
      <LeftPanel />
      <main
        className="overflow-hidden flex flex-col bg-background"
        style={{ gridArea: "main" }}
      >
        {graphModeActive ? <GraphMode /> : <MainPanel />}
      </main>
      {!graphModeActive && !authoringMode && <RightPanel />}
      <StatusBar />
      <CmdKPalette />
    </div>
  );
}
