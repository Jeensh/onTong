"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronRight, ChevronDown, X } from "lucide-react";
import type { MetadataTemplates } from "@/types";

interface DomainProcessPickerProps {
  domain: string;
  process: string;
  templates: MetadataTemplates;
  onChange: (domain: string, process: string) => void;
}

export function DomainProcessPicker({
  domain,
  process,
  templates,
  onChange,
}: DomainProcessPickerProps) {
  const [open, setOpen] = useState(false);
  const [expandedDomain, setExpandedDomain] = useState<string | null>(domain || null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const handleDomainToggle = useCallback((d: string) => {
    setExpandedDomain((prev) => (prev === d ? null : d));
  }, []);

  const handleDomainSelect = useCallback(
    (d: string) => {
      // Selecting domain only (no process)
      onChange(d, "");
      setOpen(false);
    },
    [onChange]
  );

  const handleProcessSelect = useCallback(
    (d: string, p: string) => {
      onChange(d, p);
      setOpen(false);
    },
    [onChange]
  );

  const handleClear = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onChange("", "");
    },
    [onChange]
  );

  const displayValue = domain
    ? process
      ? `${domain} / ${process}`
      : domain
    : "";

  const domainList = Object.keys(templates.domain_processes).sort();

  return (
    <div ref={containerRef} className="relative">
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground whitespace-nowrap">
          Domain / Process
        </span>
        <button
          type="button"
          className="h-7 min-w-[140px] rounded-md border border-input bg-background px-2 text-xs text-left flex items-center justify-between gap-1 outline-none focus:border-ring focus:ring-1 focus:ring-ring/50"
          onClick={() => setOpen(!open)}
        >
          <span className={displayValue ? "text-foreground" : "text-muted-foreground"}>
            {displayValue || "선택..."}
          </span>
          <span className="flex items-center gap-0.5">
            {displayValue && (
              <span
                role="button"
                className="rounded-full hover:bg-muted-foreground/20 p-0.5"
                onClick={handleClear}
              >
                <X className="h-3 w-3 text-muted-foreground" />
              </span>
            )}
            <ChevronDown className={`h-3 w-3 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} />
          </span>
        </button>
      </div>

      {open && (
        <div className="absolute z-50 mt-1 w-64 rounded-md border bg-popover shadow-md max-h-64 overflow-auto">
          {domainList.length === 0 && (
            <div className="px-3 py-2 text-xs text-muted-foreground">도메인 없음</div>
          )}
          {domainList.map((d) => {
            const processes = templates.domain_processes[d] || [];
            const isExpanded = expandedDomain === d;
            const isDomainSelected = domain === d;

            return (
              <div key={d}>
                <div
                  className={`flex items-center px-2 py-1.5 text-sm cursor-pointer hover:bg-accent ${
                    isDomainSelected && !process ? "bg-accent/60 font-medium" : ""
                  }`}
                >
                  {/* Expand toggle */}
                  <button
                    type="button"
                    className="p-0.5 rounded hover:bg-muted-foreground/20 mr-1"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDomainToggle(d);
                    }}
                  >
                    {isExpanded ? (
                      <ChevronDown className="h-3 w-3 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-3 w-3 text-muted-foreground" />
                    )}
                  </button>
                  {/* Domain name — click to select domain only */}
                  <span
                    className="flex-1"
                    onClick={() => handleDomainSelect(d)}
                  >
                    {d}
                  </span>
                  <span className="text-[10px] text-muted-foreground ml-1">
                    {processes.length}
                  </span>
                </div>

                {/* Lazy-rendered process list */}
                {isExpanded && processes.length > 0 && (
                  <div className="ml-5 border-l border-border/50">
                    {processes.map((p) => (
                      <button
                        key={p}
                        type="button"
                        className={`w-full text-left px-3 py-1 text-xs hover:bg-accent ${
                          isDomainSelected && process === p
                            ? "bg-accent/60 font-medium"
                            : "text-muted-foreground"
                        }`}
                        onClick={() => handleProcessSelect(d, p)}
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
