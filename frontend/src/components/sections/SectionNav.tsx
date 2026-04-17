"use client";

import { BookOpen, Cpu, BarChart3 } from "lucide-react";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import type { SectionId } from "@/types";
import { cn } from "@/lib/utils";

const SECTIONS: {
  id: SectionId;
  label: string;
  icon: React.ReactNode;
  status: "active" | "scaffolding";
}[] = [
  { id: "wiki", label: "Wiki", icon: <BookOpen className="w-3.5 h-3.5" />, status: "active" },
  { id: "modeling", label: "Modeling", icon: <Cpu className="w-3.5 h-3.5" />, status: "active" },
  { id: "simulation", label: "Simulation", icon: <BarChart3 className="w-3.5 h-3.5" />, status: "scaffolding" },
];

export function SectionNav() {
  const activeSection = useWorkspaceStore((s) => s.activeSection);
  const setActiveSection = useWorkspaceStore((s) => s.setActiveSection);

  return (
    <nav className="flex items-center h-10 px-3 border-b bg-background">
      {/* Brand */}
      <span className="text-sm font-semibold tracking-tight text-foreground mr-5 select-none">
        <span className="text-primary">on</span>Tong
      </span>

      {/* Section tabs */}
      <div className="flex items-center gap-0.5">
        {SECTIONS.map((section) => (
          <button
            key={section.id}
            onClick={() => setActiveSection(section.id)}
            className={cn(
              "flex items-center gap-1.5 px-2.5 py-1 text-[13px] rounded-md transition-colors",
              activeSection === section.id
                ? "text-foreground font-medium bg-muted"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
            )}
          >
            {section.icon}
            {section.label}
            {section.status === "scaffolding" && (
              <span className="text-[9px] px-1 py-px rounded bg-muted-foreground/10 text-muted-foreground leading-none">
                soon
              </span>
            )}
          </button>
        ))}
      </div>
    </nav>
  );
}
