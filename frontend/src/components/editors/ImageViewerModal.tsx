"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { X, Square, Circle, ArrowRight, Type, ZoomIn, ZoomOut, Save } from "lucide-react";
import { uploadImage } from "@/lib/clipboard/imagePaste";

type AnnotationTool = "select" | "rect" | "ellipse" | "arrow" | "text";

interface ImageViewerModalProps {
  src: string;
  filename: string;
  onClose: () => void;
  onReplace?: (newSrc: string) => void;
}

interface ImageMeta {
  filename: string;
  size_bytes: number;
  width: number;
  height: number;
  ref_count: number;
  referenced_by: string[];
  source: string | null;
  has_ocr: boolean;
  ocr_text?: string;
  description?: string;
}

export function ImageViewerModal({ src, filename, onClose, onReplace }: ImageViewerModalProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fabricRef = useRef<any>(null);
  const [editing, setEditing] = useState(false);
  const [activeTool, setActiveTool] = useState<AnnotationTool>("select");
  const [color, setColor] = useState("#e94560");
  const [meta, setMeta] = useState<ImageMeta | null>(null);
  const [saving, setSaving] = useState(false);

  // Load image metadata
  useEffect(() => {
    fetch(`/api/files/assets/${filename}.meta.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data) {
          setMeta((prev) => ({
            ...prev,
            filename,
            ocr_text: data.ocr_text || "",
            description: data.description || "",
            source: data.source || null,
            has_ocr: !!(data.ocr_text || data.description),
          } as ImageMeta));
        }
      })
      .catch(() => {});

    fetch(`/api/files/assets?search=${encodeURIComponent(filename)}&size=1`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.items?.[0]) {
          setMeta((prev) => ({ ...prev, ...data.items[0] }));
        }
      })
      .catch(() => {});
  }, [filename]);

  // Initialize fabric.js canvas
  useEffect(() => {
    if (!canvasRef.current) return;

    let mounted = true;

    (async () => {
      const fabricModule = await import("fabric");
      const { Canvas, FabricImage } = fabricModule;

      if (!mounted || !canvasRef.current) return;

      const container = canvasRef.current.parentElement;
      if (!container) return;

      const canvas = new Canvas(canvasRef.current, {
        width: container.clientWidth,
        height: container.clientHeight,
        selection: editing,
      });

      fabricRef.current = canvas;

      const img = await FabricImage.fromURL(src, { crossOrigin: "anonymous" });

      const scaleX = canvas.width! / (img.width || 1);
      const scaleY = canvas.height! / (img.height || 1);
      const scale = Math.min(scaleX, scaleY, 1) * 0.9;

      img.set({
        scaleX: scale,
        scaleY: scale,
        left: (canvas.width! - (img.width || 0) * scale) / 2,
        top: (canvas.height! - (img.height || 0) * scale) / 2,
        selectable: false,
        evented: false,
      });

      canvas.add(img);
      canvas.sendObjectToBack(img);
      canvas.renderAll();
    })();

    return () => {
      mounted = false;
      if (fabricRef.current) {
        fabricRef.current.dispose();
        fabricRef.current = null;
      }
    };
  }, [src, editing]);

  // Handle tool changes
  useEffect(() => {
    const canvas = fabricRef.current;
    if (!canvas || !editing) return;

    canvas.isDrawingMode = false;
    canvas.selection = activeTool === "select";

    canvas.off("mouse:down");
    canvas.off("mouse:move");
    canvas.off("mouse:up");

    if (activeTool === "rect") {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let startX = 0, startY = 0, rect: any = null;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      canvas.on("mouse:down", (opt: any) => {
        if (opt.target) return;
        const pointer = canvas.getScenePoint(opt.e);
        startX = pointer.x;
        startY = pointer.y;
        import("fabric").then(({ Rect }) => {
          rect = new Rect({
            left: startX, top: startY, width: 0, height: 0,
            fill: "transparent", stroke: color, strokeWidth: 3,
          });
          canvas.add(rect);
        });
      });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      canvas.on("mouse:move", (opt: any) => {
        if (!rect) return;
        const pointer = canvas.getScenePoint(opt.e);
        rect.set({
          width: Math.abs(pointer.x - startX),
          height: Math.abs(pointer.y - startY),
          left: Math.min(startX, pointer.x),
          top: Math.min(startY, pointer.y),
        });
        canvas.renderAll();
      });
      canvas.on("mouse:up", () => { rect = null; });
    }

    if (activeTool === "ellipse") {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let startX = 0, startY = 0, ellipse: any = null;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      canvas.on("mouse:down", (opt: any) => {
        if (opt.target) return;
        const pointer = canvas.getScenePoint(opt.e);
        startX = pointer.x;
        startY = pointer.y;
        import("fabric").then(({ Ellipse }) => {
          ellipse = new Ellipse({
            left: startX, top: startY, rx: 0, ry: 0,
            fill: "transparent", stroke: color, strokeWidth: 3,
          });
          canvas.add(ellipse);
        });
      });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      canvas.on("mouse:move", (opt: any) => {
        if (!ellipse) return;
        const pointer = canvas.getScenePoint(opt.e);
        ellipse.set({
          rx: Math.abs(pointer.x - startX) / 2,
          ry: Math.abs(pointer.y - startY) / 2,
          left: Math.min(startX, pointer.x),
          top: Math.min(startY, pointer.y),
        });
        canvas.renderAll();
      });
      canvas.on("mouse:up", () => { ellipse = null; });
    }

    if (activeTool === "arrow") {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let startX = 0, startY = 0, line: any = null;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      canvas.on("mouse:down", (opt: any) => {
        if (opt.target) return;
        const pointer = canvas.getScenePoint(opt.e);
        startX = pointer.x;
        startY = pointer.y;
        import("fabric").then(({ Line }) => {
          line = new Line([startX, startY, startX, startY], {
            stroke: color, strokeWidth: 3,
          });
          canvas.add(line);
        });
      });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      canvas.on("mouse:move", (opt: any) => {
        if (!line) return;
        const pointer = canvas.getScenePoint(opt.e);
        line.set({ x2: pointer.x, y2: pointer.y });
        canvas.renderAll();
      });
      canvas.on("mouse:up", () => { line = null; });
    }

    if (activeTool === "text") {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      canvas.on("mouse:down", (opt: any) => {
        if (opt.target) return;
        const pointer = canvas.getScenePoint(opt.e);
        import("fabric").then(({ IText }) => {
          const text = new IText("텍스트", {
            left: pointer.x, top: pointer.y,
            fontSize: 20, fill: color,
            fontFamily: "sans-serif",
          });
          canvas.add(text);
          canvas.setActiveObject(text);
          text.enterEditing();
        });
      });
    }
  }, [activeTool, color, editing]);

  const handleSave = useCallback(async () => {
    const canvas = fabricRef.current;
    if (!canvas) return;
    setSaving(true);

    try {
      const dataUrl = canvas.toDataURL({ format: "png", multiplier: 1 });
      const res = await fetch(dataUrl);
      const blob = await res.blob();
      const file = new File([blob], "annotated.png", { type: "image/png" });

      const path = await uploadImage(file);

      const newFilename = path.split("/").pop() || "";
      const inheritOcr = window.confirm(
        "원본 OCR 텍스트를 상속하시겠습니까?\n\n" +
        "확인: 원본 OCR 상속\n취소: 새로 OCR 처리 (저장 후 자동 실행)"
      );

      if (inheritOcr) {
        await fetch(`/api/files/assets/${newFilename}/inherit-ocr`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source_filename: filename }),
        });
      }

      if (onReplace) {
        onReplace(`/api/files/${path}`);
      }
      onClose();
    } catch (err) {
      console.error("Failed to save annotation:", err);
      alert("저장 실패: " + (err as Error).message);
    } finally {
      setSaving(false);
    }
  }, [filename, onClose, onReplace]);

  // Close on Escape
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex" onClick={(e) => e.target === e.currentTarget && onClose()}>
      {/* Left toolbar */}
      <div className="w-11 bg-gray-900 flex flex-col items-center py-3 gap-2">
        {editing && (
          <>
            {([
              ["select", "선택"],
              ["rect", "사각형"],
              ["ellipse", "타원"],
              ["arrow", "화살표"],
              ["text", "텍스트"],
            ] as const).map(([tool, label]) => (
              <button
                key={tool}
                onClick={() => setActiveTool(tool as AnnotationTool)}
                className={`w-8 h-8 rounded flex items-center justify-center text-xs ${
                  activeTool === tool ? "bg-red-500 text-white" : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                }`}
                title={label}
              >
                {tool === "rect" && <Square size={14} />}
                {tool === "ellipse" && <Circle size={14} />}
                {tool === "arrow" && <ArrowRight size={14} />}
                {tool === "text" && <Type size={14} />}
                {tool === "select" && <span>↖</span>}
              </button>
            ))}
            <div className="my-1 border-t border-gray-700 w-6" />
            <input
              type="color"
              value={color}
              onChange={(e) => setColor(e.target.value)}
              className="w-7 h-7 rounded cursor-pointer border-0"
              title="색상"
            />
          </>
        )}
        <div className="flex-1" />
        <button
          onClick={() => {
            const canvas = fabricRef.current;
            if (canvas) canvas.setZoom(canvas.getZoom() * 1.2);
          }}
          className="w-8 h-8 rounded bg-gray-700 text-gray-300 hover:bg-gray-600 flex items-center justify-center"
          title="확대"
        >
          <ZoomIn size={14} />
        </button>
        <button
          onClick={() => {
            const canvas = fabricRef.current;
            if (canvas) canvas.setZoom(canvas.getZoom() / 1.2);
          }}
          className="w-8 h-8 rounded bg-gray-700 text-gray-300 hover:bg-gray-600 flex items-center justify-center"
          title="축소"
        >
          <ZoomOut size={14} />
        </button>
      </div>

      {/* Center canvas */}
      <div className="flex-1 flex items-center justify-center relative">
        <canvas ref={canvasRef} />
        <button
          onClick={onClose}
          className="absolute top-3 right-3 w-8 h-8 rounded-full bg-gray-800/80 text-white flex items-center justify-center hover:bg-gray-700"
        >
          <X size={16} />
        </button>
      </div>

      {/* Right info panel */}
      <div className="w-52 bg-gray-900 text-gray-300 p-3 text-xs overflow-y-auto">
        <div className="text-red-400 font-bold mb-2">이미지 정보</div>
        <div className="space-y-1 mb-4">
          <div>파일: {filename}</div>
          {meta && (
            <>
              <div>크기: {meta.width} x {meta.height}</div>
              <div>용량: {formatBytes(meta.size_bytes)}</div>
              <div>참조: {meta.ref_count ?? "?"}개 문서</div>
              {meta.source && <div className="text-purple-400">원본: {meta.source}</div>}
            </>
          )}
        </div>

        {meta?.ocr_text && (
          <>
            <div className="text-red-400 font-bold mb-2">OCR 텍스트</div>
            <div className="text-gray-400 text-[10px] leading-relaxed mb-4 max-h-40 overflow-y-auto">
              {meta.ocr_text}
            </div>
          </>
        )}

        {meta?.description && (
          <>
            <div className="text-red-400 font-bold mb-2">설명</div>
            <div className="text-gray-400 text-[10px] leading-relaxed mb-4 max-h-40 overflow-y-auto">
              {meta.description}
            </div>
          </>
        )}

        {meta?.referenced_by && meta.referenced_by.length > 0 && (
          <>
            <div className="text-red-400 font-bold mb-2">참조 문서</div>
            <div className="space-y-1 mb-4">
              {meta.referenced_by.map((doc) => (
                <div key={doc} className="text-blue-400 text-[10px] truncate">{doc}</div>
              ))}
            </div>
          </>
        )}

        <div className="mt-4 space-y-2">
          {!editing ? (
            <button
              onClick={() => setEditing(true)}
              className="w-full py-1.5 bg-red-500 text-white rounded text-xs hover:bg-red-600"
            >
              편집
            </button>
          ) : (
            <>
              <button
                onClick={handleSave}
                disabled={saving}
                className="w-full py-1.5 bg-red-500 text-white rounded text-xs hover:bg-red-600 disabled:opacity-50 flex items-center justify-center gap-1"
              >
                <Save size={12} />
                {saving ? "저장 중..." : "새 이미지로 저장"}
              </button>
              <button
                onClick={() => setEditing(false)}
                className="w-full py-1.5 bg-gray-700 text-gray-300 rounded text-xs hover:bg-gray-600"
              >
                취소
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (!bytes) return "?";
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}
