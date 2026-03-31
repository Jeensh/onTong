"use client";

import { useCallback, useRef, useState } from "react";

interface ImageViewerProps {
  filePath: string;
}

export function ImageViewer({ filePath }: ImageViewerProps) {
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const posStart = useRef({ x: 0, y: 0 });

  const zoomIn = useCallback(() => setScale((s) => Math.min(s * 1.25, 5)), []);
  const zoomOut = useCallback(() => setScale((s) => Math.max(s / 1.25, 0.1)), []);
  const resetZoom = useCallback(() => {
    setScale(1);
    setPosition({ x: 0, y: 0 });
  }, []);

  function handleWheel(e: React.WheelEvent) {
    e.preventDefault();
    if (e.deltaY < 0) zoomIn();
    else zoomOut();
  }

  function handleMouseDown(e: React.MouseEvent) {
    if (e.button !== 0) return;
    setDragging(true);
    dragStart.current = { x: e.clientX, y: e.clientY };
    posStart.current = { ...position };
  }

  function handleMouseMove(e: React.MouseEvent) {
    if (!dragging) return;
    setPosition({
      x: posStart.current.x + (e.clientX - dragStart.current.x),
      y: posStart.current.y + (e.clientY - dragStart.current.y),
    });
  }

  function handleMouseUp() {
    setDragging(false);
  }

  const src = `/api/files/${filePath}`;

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-1.5 border-b bg-muted/30">
        <button
          onClick={zoomOut}
          className="px-2 py-0.5 text-xs rounded hover:bg-muted"
          title="축소"
        >
          −
        </button>
        <span className="text-xs text-muted-foreground min-w-[50px] text-center">
          {Math.round(scale * 100)}%
        </span>
        <button
          onClick={zoomIn}
          className="px-2 py-0.5 text-xs rounded hover:bg-muted"
          title="확대"
        >
          +
        </button>
        <button
          onClick={resetZoom}
          className="px-2 py-0.5 text-xs rounded hover:bg-muted"
          title="초기화"
        >
          1:1
        </button>
        <div className="flex-1" />
        <span className="text-xs text-muted-foreground">{filePath}</span>
      </div>

      {/* Canvas area */}
      <div
        className="flex-1 overflow-hidden bg-muted/20 flex items-center justify-center"
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{ cursor: dragging ? "grabbing" : "grab" }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={filePath}
          draggable={false}
          style={{
            transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
            transformOrigin: "center center",
            maxWidth: "none",
            transition: dragging ? "none" : "transform 0.1s ease-out",
          }}
        />
      </div>
    </div>
  );
}
