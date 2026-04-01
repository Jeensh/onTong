"use client";

import { useEffect } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { TreeNav } from "@/components/TreeNav";
import { WorkspacePanel } from "@/components/workspace/WorkspacePanel";
import { AICopilot } from "@/components/AICopilot";
import { SearchCommandPalette } from "@/components/search/SearchCommandPalette";
import { useSearchStore } from "@/lib/search/useSearchStore";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import { SectionNav } from "@/components/sections/SectionNav";
import { SimulationSection } from "@/components/simulation/SimulationSection";
import { ModelingSection } from "@/components/sections/ModelingSection";

export default function Home() {
  const toggle = useSearchStore((s) => s.toggle);
  const activeSection = useWorkspaceStore((s) => s.activeSection);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        toggle();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [toggle]);

  return (
    <div className="h-screen flex flex-col">
      <SectionNav />
      <SearchCommandPalette />
      <div className="flex-1 min-h-0">
        {activeSection === "wiki" && (
          <PanelGroup direction="horizontal" className="h-full">
            {/* Left: TreeNav */}
            <Panel defaultSize={20} minSize={12} maxSize={35}>
              <div className="h-full overflow-auto border-r">
                <TreeNav />
              </div>
            </Panel>

            <PanelResizeHandle className="w-1 bg-border hover:bg-primary/30 transition-colors cursor-col-resize" />

            {/* Center: Workspace */}
            <Panel defaultSize={55} minSize={30}>
              <WorkspacePanel />
            </Panel>

            <PanelResizeHandle className="w-1 bg-border hover:bg-primary/30 transition-colors cursor-col-resize" />

            {/* Right: AI Copilot */}
            <Panel defaultSize={25} minSize={15} maxSize={40}>
              <div className="h-full border-l">
                <AICopilot />
              </div>
            </Panel>
          </PanelGroup>
        )}

        {activeSection === "modeling" && <ModelingSection />}

        {activeSection === "simulation" && <SimulationSection />}
      </div>
    </div>
  );
}
