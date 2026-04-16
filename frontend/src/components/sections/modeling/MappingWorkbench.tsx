"use client";

import React, { useCallback, useRef, useState } from "react";
import { MappingCanvas } from "./MappingCanvas";
import { SourceViewer } from "./SourceViewer";

interface MappingWorkbenchProps {
  repoId: string;
}

export function MappingWorkbench({ repoId }: MappingWorkbenchProps) {
  const [splitPercent, setSplitPercent] = useState(55);
  const [highlightEntity, setHighlightEntity] = useState<string | null>(null);
  const [highlightDomain, setHighlightDomain] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);

  // Canvas → Viewer: domain node clicked → show connected entities' source
  const handleDomainNodeClick = useCallback((nodeId: string, mappedEntities: string[]) => {
    setHighlightDomain(null);
    if (mappedEntities.length > 0) {
      setHighlightEntity(mappedEntities[0]);
    }
  }, []);

  // Viewer → Canvas: entity clicked in source → highlight domain node
  const handleEntityClickInViewer = useCallback((fqn: string, _filePath: string) => {
    setHighlightEntity(null);
    // The canvas will highlight the domain node connected to this entity
    setHighlightDomain(fqn);
  }, []);

  // Canvas entity panel → Viewer: entity clicked → open its file
  const handleEntityClickInCanvas = useCallback((fqn: string) => {
    setHighlightEntity(fqn);
  }, []);

  // Resizer
  const handleMouseDown = useCallback(() => {
    isDragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const percent = ((e.clientX - rect.left) / rect.width) * 100;
      setSplitPercent(Math.min(Math.max(percent, 25), 75));
    };

    const handleMouseUp = () => {
      isDragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
  }, []);

  return (
    <div ref={containerRef} className="flex h-full">
      {/* Left: Mapping Canvas */}
      <div style={{ width: `${splitPercent}%` }} className="h-full overflow-hidden">
        <MappingCanvas
          repoId={repoId}
          onDomainNodeClick={handleDomainNodeClick}
          onEntityClick={handleEntityClickInCanvas}
          highlightDomainNode={highlightDomain}
        />
      </div>

      {/* Resizer */}
      <div
        onMouseDown={handleMouseDown}
        className="w-1 bg-border hover:bg-primary/50 cursor-col-resize shrink-0 transition-colors"
      />

      {/* Right: Source Viewer */}
      <div style={{ width: `${100 - splitPercent}%` }} className="h-full overflow-hidden">
        <SourceViewer
          repoId={repoId}
          highlightEntity={highlightEntity}
          onEntityClick={handleEntityClickInViewer}
        />
      </div>
    </div>
  );
}
