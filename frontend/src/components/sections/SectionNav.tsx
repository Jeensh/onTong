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
  { id: "wiki", label: "Wiki", icon: <BookOpen className="w-4 h-4" />, status: "active" },
  { id: "modeling", label: "Modeling", icon: <Cpu className="w-4 h-4" />, status: "scaffolding" },
  { id: "simulation", label: "Simulation", icon: <BarChart3 className="w-4 h-4" />, status: "scaffolding" },
];

export function SectionNav() {
  const activeSection = useWorkspaceStore((s) => s.activeSection);
  const setActiveSection = useWorkspaceStore((s) => s.setActiveSection);

  return (
    <nav className="flex items-center h-10 px-3 border-b bg-muted/30 gap-1">
      <span className="text-sm font-semibold text-foreground mr-3">onTong</span>
      <div className="flex gap-0.5">
        {SECTIONS.map((section) => (
          <button
            key={section.id}
            onClick={() => setActiveSection(section.id)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md transition-colors",
              activeSection === section.id
                ? "bg-background text-foreground shadow-sm font-medium"
                : "text-muted-foreground hover:text-foreground hover:bg-muted",
            )}
          >
            {section.icon}
            {section.label}
            {section.status === "scaffolding" && (
              <span className="text-[10px] px-1 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300 leading-none">
                준비중
              </span>
            )}
          </button>
        ))}
      </div>
    </nav>
  );
}
