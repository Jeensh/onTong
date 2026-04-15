"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Panel,
  PanelGroup,
  PanelResizeHandle,
  type ImperativePanelHandle,
} from "react-resizable-panels";
import { TreeNav } from "@/components/TreeNav";
import { WorkspacePanel } from "@/components/workspace/WorkspacePanel";
import { AICopilot } from "@/components/AICopilot";
import { SearchCommandPalette } from "@/components/search/SearchCommandPalette";
import { useSearchStore } from "@/lib/search/useSearchStore";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import { SectionNav } from "@/components/sections/SectionNav";
import { SimulationSection } from "@/components/simulation/SimulationSection";
import { ModelingSection } from "@/components/sections/ModelingSection";
import { FolderTree, Sparkles, PanelRightClose } from "lucide-react";

function readBool(key: string, fallback: boolean): boolean {
  if (typeof window === "undefined") return fallback;
  const v = localStorage.getItem(key);
  return v === null ? fallback : v === "true";
}

export default function Home() {
  const toggle = useSearchStore((s) => s.toggle);
  const activeSection = useWorkspaceStore((s) => s.activeSection);

  const treePanelRef = useRef<ImperativePanelHandle>(null);
  const aiPanelRef = useRef<ImperativePanelHandle>(null);
  const [treeCollapsed, setTreeCollapsed] = useState(() => readBool("ontong_panel_tree_collapsed", false));
  const [aiCollapsed, setAiCollapsed] = useState(() => readBool("ontong_panel_ai_collapsed", false));
  const [aiPopout, setAiPopout] = useState(false);

  // Popout floating window drag state
  const [popoutPos, setPopoutPos] = useState({ x: 0, y: 0 });
  const [popoutSize, setPopoutSize] = useState({ w: 480, h: 600 });
  const dragRef = useRef<{ startX: number; startY: number; origX: number; origY: number } | null>(null);
  const resizeRef = useRef<{ startX: number; startY: number; origW: number; origH: number } | null>(null);

  // Initialize popout position to bottom-right
  useEffect(() => {
    if (typeof window !== "undefined") {
      setPopoutPos({ x: window.innerWidth - 500, y: window.innerHeight - 640 });
    }
  }, []);

  const handleTreeCollapse = useCallback(() => {
    setTreeCollapsed(true);
    localStorage.setItem("ontong_panel_tree_collapsed", "true");
  }, []);
  const handleTreeExpand = useCallback(() => {
    setTreeCollapsed(false);
    localStorage.setItem("ontong_panel_tree_collapsed", "false");
  }, []);
  const handleAiCollapse = useCallback(() => {
    setAiCollapsed(true);
    localStorage.setItem("ontong_panel_ai_collapsed", "true");
  }, []);
  const handleAiExpand = useCallback(() => {
    setAiCollapsed(false);
    localStorage.setItem("ontong_panel_ai_collapsed", "false");
  }, []);

  const handlePopout = useCallback(() => {
    setAiPopout(true);
    // Collapse the panel when popping out
    aiPanelRef.current?.collapse();
  }, []);

  const handleDockBack = useCallback(() => {
    setAiPopout(false);
    // Expand the panel when docking back
    aiPanelRef.current?.expand();
  }, []);

  // Restore collapsed state from localStorage on mount
  useEffect(() => {
    if (readBool("ontong_panel_tree_collapsed", false)) {
      treePanelRef.current?.collapse();
    }
    if (readBool("ontong_panel_ai_collapsed", false)) {
      aiPanelRef.current?.collapse();
    }
  }, []);

  // Drag handler for popout window
  useEffect(() => {
    if (!aiPopout) return;
    const onMouseMove = (e: MouseEvent) => {
      if (dragRef.current) {
        const dx = e.clientX - dragRef.current.startX;
        const dy = e.clientY - dragRef.current.startY;
        setPopoutPos({ x: dragRef.current.origX + dx, y: dragRef.current.origY + dy });
      }
      if (resizeRef.current) {
        const dw = e.clientX - resizeRef.current.startX;
        const dh = e.clientY - resizeRef.current.startY;
        setPopoutSize({
          w: Math.max(360, resizeRef.current.origW + dw),
          h: Math.max(300, resizeRef.current.origH + dh),
        });
      }
    };
    const onMouseUp = () => {
      dragRef.current = null;
      resizeRef.current = null;
    };
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
    return () => {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };
  }, [aiPopout]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        toggle();
        return;
      }
      // Cmd+B: toggle tree sidebar
      if ((e.metaKey || e.ctrlKey) && e.key === "b") {
        e.preventDefault();
        const panel = treePanelRef.current;
        if (!panel) return;
        if (treeCollapsed) panel.expand();
        else panel.collapse();
        return;
      }
      // Cmd+J: toggle AI copilot (popout or panel)
      if ((e.metaKey || e.ctrlKey) && e.key === "j") {
        e.preventDefault();
        if (aiPopout) {
          handleDockBack();
        } else {
          const panel = aiPanelRef.current;
          if (!panel) return;
          if (aiCollapsed) panel.expand();
          else panel.collapse();
        }
        return;
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [toggle, treeCollapsed, aiCollapsed, aiPopout, handleDockBack]);

  return (
    <div className="h-screen flex flex-col">
      <SectionNav />
      <SearchCommandPalette />
      <div className="flex-1 min-h-0">
        {activeSection === "wiki" && (
          <div className="flex h-full">
            {/* Collapsed strip for tree */}
            {treeCollapsed && (
              <button
                onClick={() => treePanelRef.current?.expand()}
                className="w-7 flex flex-col items-center justify-center border-r bg-muted/30 hover:bg-muted/60 transition-colors shrink-0"
                title="사이드바 열기 (⌘B)"
              >
                <FolderTree className="h-4 w-4 text-muted-foreground" />
              </button>
            )}

            <PanelGroup direction="horizontal" className="h-full flex-1">
              {/* Left: TreeNav (collapsible) */}
              <Panel
                ref={treePanelRef}
                defaultSize={20}
                minSize={12}
                maxSize={35}
                collapsible={true}
                collapsedSize={0}
                onCollapse={handleTreeCollapse}
                onExpand={handleTreeExpand}
              >
                <div className="h-full overflow-auto border-r">
                  <TreeNav />
                </div>
              </Panel>

              <PanelResizeHandle className="w-1.5 bg-transparent hover:bg-primary/20 active:bg-primary/30 transition-colors cursor-col-resize group relative after:absolute after:inset-y-0 after:-inset-x-1 after:content-['']" />

              {/* Center: Workspace */}
              <Panel defaultSize={55} minSize={30}>
                <WorkspacePanel />
              </Panel>

              <PanelResizeHandle className="w-1.5 bg-transparent hover:bg-primary/20 active:bg-primary/30 transition-colors cursor-col-resize group relative after:absolute after:inset-y-0 after:-inset-x-1 after:content-['']" />

              {/* Right: AI Copilot (collapsible) */}
              <Panel
                ref={aiPanelRef}
                defaultSize={25}
                minSize={15}
                maxSize={40}
                collapsible={true}
                collapsedSize={0}
                onCollapse={handleAiCollapse}
                onExpand={handleAiExpand}
              >
                <div className="h-full border-l">
                  {!aiPopout && <AICopilot onPopout={handlePopout} />}
                </div>
              </Panel>
            </PanelGroup>

            {/* Collapsed strip for AI */}
            {aiCollapsed && !aiPopout && (
              <button
                onClick={() => aiPanelRef.current?.expand()}
                className="w-7 flex flex-col items-center justify-center border-l bg-muted/30 hover:bg-muted/60 transition-colors shrink-0"
                title="AI 코파일럿 열기 (⌘J)"
              >
                <Sparkles className="h-4 w-4 text-muted-foreground" />
              </button>
            )}

            {/* Popout strip when AI is popped out and panel is collapsed */}
            {aiPopout && aiCollapsed && (
              <button
                onClick={handleDockBack}
                className="w-7 flex flex-col items-center justify-center border-l bg-primary/10 hover:bg-primary/20 transition-colors shrink-0"
                title="AI 코파일럿 패널로 되돌리기 (⌘J)"
              >
                <PanelRightClose className="h-4 w-4 text-primary" />
              </button>
            )}
          </div>
        )}

        {activeSection === "modeling" && <ModelingSection />}

        {activeSection === "simulation" && <SimulationSection />}
      </div>

      {/* Floating popout AI window */}
      {aiPopout && activeSection === "wiki" && (
        <div
          className="fixed z-50 rounded-lg border shadow-2xl bg-background flex flex-col overflow-hidden"
          style={{
            left: popoutPos.x,
            top: popoutPos.y,
            width: popoutSize.w,
            height: popoutSize.h,
          }}
        >
          {/* Draggable header area — drag starts on the header bar inside AICopilot */}
          <div
            className="flex-1 min-h-0 cursor-move"
            onMouseDown={(e) => {
              // Only initiate drag from the header area (first 44px)
              const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
              if (e.clientY - rect.top < 44) {
                dragRef.current = { startX: e.clientX, startY: e.clientY, origX: popoutPos.x, origY: popoutPos.y };
              }
            }}
          >
            <AICopilot onDockBack={handleDockBack} isPopout />
          </div>

          {/* Resize handle (bottom-right corner) */}
          <div
            className="absolute bottom-0 right-0 w-4 h-4 cursor-se-resize"
            onMouseDown={(e) => {
              e.stopPropagation();
              resizeRef.current = { startX: e.clientX, startY: e.clientY, origW: popoutSize.w, origH: popoutSize.h };
            }}
          >
            <svg className="w-4 h-4 text-muted-foreground/50" viewBox="0 0 16 16" fill="currentColor">
              <path d="M14 14H12V12H14V14ZM14 10H12V8H14V10ZM10 14H8V12H10V14Z" />
            </svg>
          </div>
        </div>
      )}
    </div>
  );
}
