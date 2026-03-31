"use client";

import { useCallback, useEffect, useState } from "react";

interface PresentationViewerProps {
  filePath: string;
}

interface TextRun {
  text: string;
  bold?: boolean;
  italic?: boolean;
  fontSize?: number;
  color?: string;
}

interface Paragraph {
  runs: TextRun[];
  align?: string;
}

interface SlideElement {
  type: "text" | "image";
  left: number;
  top: number;
  width: number;
  height: number;
  paragraphs?: Paragraph[];
  src?: string;
}

interface Slide {
  elements: SlideElement[];
}

interface PptxData {
  slideWidth: number;
  slideHeight: number;
  totalSlides: number;
  slides: Slide[];
}

export function PresentationViewer({ filePath }: PresentationViewerProps) {
  const [data, setData] = useState<PptxData | null>(null);
  const [currentSlide, setCurrentSlide] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetch(`/api/files/pptx-data/${filePath}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json: PptxData) => {
        if (!cancelled) {
          setData(json);
          setCurrentSlide(0);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [filePath]);

  const totalSlides = data?.totalSlides ?? 0;

  const goToSlide = useCallback(
    (idx: number) => {
      setCurrentSlide(Math.max(0, Math.min(idx, totalSlides - 1)));
    },
    [totalSlides],
  );

  // Keyboard navigation
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
        e.preventDefault();
        goToSlide(currentSlide - 1);
      } else if (e.key === "ArrowRight" || e.key === "ArrowDown" || e.key === " ") {
        e.preventDefault();
        goToSlide(currentSlide + 1);
      } else if (e.key === "Home") {
        e.preventDefault();
        goToSlide(0);
      } else if (e.key === "End") {
        e.preventDefault();
        goToSlide(totalSlides - 1);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [currentSlide, goToSlide, totalSlides]);

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-destructive">
        <div className="text-center">
          <p className="text-sm font-medium">PPTX 로드 실패</p>
          <p className="text-xs mt-1 text-muted-foreground">{error}</p>
        </div>
      </div>
    );
  }

  const slide = data?.slides[currentSlide];
  const sw = data?.slideWidth ?? 13.33;
  const sh = data?.slideHeight ?? 7.5;

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-1.5 border-b bg-muted/30 shrink-0">
        <button
          onClick={() => goToSlide(currentSlide - 1)}
          disabled={currentSlide <= 0 || loading}
          className="px-2 py-0.5 text-xs rounded hover:bg-muted disabled:opacity-30"
          title="이전 슬라이드"
        >
          ◀
        </button>
        <div className="flex items-center gap-1">
          <input
            type="number"
            min={1}
            max={totalSlides}
            value={currentSlide + 1}
            onChange={(e) => goToSlide(Number(e.target.value) - 1)}
            disabled={loading}
            className="w-12 text-center text-xs border rounded px-1 py-0.5 bg-background"
          />
          <span className="text-xs text-muted-foreground">
            / {loading ? "..." : totalSlides}
          </span>
        </div>
        <button
          onClick={() => goToSlide(currentSlide + 1)}
          disabled={currentSlide >= totalSlides - 1 || loading}
          className="px-2 py-0.5 text-xs rounded hover:bg-muted disabled:opacity-30"
          title="다음 슬라이드"
        >
          ▶
        </button>
        <div className="flex-1" />
        <span className="text-xs text-muted-foreground truncate max-w-[200px]">
          {filePath}
        </span>
      </div>

      {/* Slide content */}
      <div className="flex-1 overflow-auto flex items-center justify-center bg-neutral-200 dark:bg-neutral-800 p-4">
        {loading ? (
          <p className="text-sm text-muted-foreground">프레젠테이션 로딩 중...</p>
        ) : slide ? (
          <div
            className="relative bg-white shadow-xl"
            style={{
              width: `${sw * 72}px`,
              height: `${sh * 72}px`,
              transform: "scale(var(--slide-scale, 1))",
              transformOrigin: "center center",
            }}
          >
            <SlideRenderer slide={slide} slideWidth={sw} slideHeight={sh} />
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">슬라이드 없음</p>
        )}
      </div>
    </div>
  );
}

function SlideRenderer({ slide, slideWidth }: { slide: Slide; slideWidth: number; slideHeight: number }) {
  // Scale factor: inches to px (72 DPI base)
  const PX = 72;

  return (
    <>
      {slide.elements.map((el, i) => {
        const style: React.CSSProperties = {
          position: "absolute",
          left: `${(el.left / slideWidth) * 100}%`,
          top: `${el.top * PX}px`,
          width: `${(el.width / slideWidth) * 100}%`,
          height: `${el.height * PX}px`,
          overflow: "hidden",
        };

        if (el.type === "image" && el.src) {
          return (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              key={i}
              src={el.src}
              alt=""
              style={{ ...style, objectFit: "contain" }}
            />
          );
        }

        if (el.type === "text" && el.paragraphs) {
          return (
            <div key={i} style={style} className="flex flex-col justify-center px-2">
              {el.paragraphs.map((p, pi) => (
                <p
                  key={pi}
                  style={{ textAlign: (p.align as React.CSSProperties["textAlign"]) || "left", margin: 0 }}
                >
                  {p.runs.map((run, ri) => (
                    <span
                      key={ri}
                      style={{
                        fontWeight: run.bold ? 700 : undefined,
                        fontStyle: run.italic ? "italic" : undefined,
                        fontSize: run.fontSize ? `${run.fontSize * 0.75}px` : undefined,
                        color: run.color ? `#${run.color}` : "#333",
                      }}
                    >
                      {run.text}
                    </span>
                  ))}
                </p>
              ))}
            </div>
          );
        }

        return null;
      })}
    </>
  );
}
