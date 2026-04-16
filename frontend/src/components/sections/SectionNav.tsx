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
  { id: "modeling", label: "Modeling", icon: <Cpu className="w-4 h-4" />, status: "active" },
  { id: "simulation", label: "Simulation", icon: <BarChart3 className="w-4 h-4" />, status: "scaffolding" },
];

export function SectionNav() {
  const activeSection = useWorkspaceStore((s) => s.activeSection);
  const setActiveSection = useWorkspaceStore((s) => s.setActiveSection);

  return (
    <nav className="flex items-center h-11 px-4 border-b bg-background gap-2">
      <div className="flex items-center gap-2 mr-4">
        <div className="w-6 h-6 rounded-md bg-primary flex items-center justify-center">
          <span className="text-xs font-bold text-primary-foreground">on</span>
        </div>
        <span className="text-sm font-bold tracking-tight text-foreground">onTong</span>
      </div>
      <div className="flex gap-1">
        {SECTIONS.map((section) => (
          <button
            key={section.id}
            onClick={() => setActiveSection(section.id)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-2 text-sm rounded-md transition-colors",
              activeSection === section.id
                ? "bg-primary/10 text-primary font-medium"
                : "text-muted-foreground hover:text-foreground hover:bg-muted",
            )}
          >
            {section.icon}
            {section.label}
            {section.status === "scaffolding" && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300 leading-none font-medium">
                준비중
              </span>
            )}
          </button>
        ))}
      </div>
    </nav>
  );
}
