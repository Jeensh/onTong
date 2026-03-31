"use client";

import { useCallback, useEffect, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

interface PdfViewerProps {
  filePath: string;
}

const SCALES = [0.5, 0.75, 1, 1.25, 1.5, 2];
const PAGE_GROUP_SIZE = 50;

export function PdfViewer({ filePath }: PdfViewerProps) {
  const [numPages, setNumPages] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [scaleIdx, setScaleIdx] = useState(2); // default 100%
  const [pageGroup, setPageGroup] = useState(0); // for 50+ page pagination
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const scale = SCALES[scaleIdx];
  const src = `/api/files/${filePath}`;

  const totalGroups = Math.ceil(numPages / PAGE_GROUP_SIZE);
  const groupStart = pageGroup * PAGE_GROUP_SIZE + 1;
  const groupEnd = Math.min((pageGroup + 1) * PAGE_GROUP_SIZE, numPages);

  function onDocumentLoadSuccess({ numPages: n }: { numPages: number }) {
    setNumPages(n);
    setLoading(false);
    setError(null);
  }

  function onDocumentLoadError(err: Error) {
    setError(err.message);
    setLoading(false);
  }

  const goToPage = useCallback(
    (page: number) => {
      const clamped = Math.max(1, Math.min(page, numPages));
      setCurrentPage(clamped);
      // Auto-switch page group
      const newGroup = Math.floor((clamped - 1) / PAGE_GROUP_SIZE);
      if (newGroup !== pageGroup) setPageGroup(newGroup);
    },
    [numPages, pageGroup],
  );

  const zoomIn = useCallback(
    () => setScaleIdx((i) => Math.min(i + 1, SCALES.length - 1)),
    [],
  );
  const zoomOut = useCallback(
    () => setScaleIdx((i) => Math.max(i - 1, 0)),
    [],
  );

  // Keyboard navigation
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
        e.preventDefault();
        goToPage(currentPage - 1);
      } else if (e.key === "ArrowRight" || e.key === "ArrowDown") {
        e.preventDefault();
        goToPage(currentPage + 1);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [currentPage, goToPage]);

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-1.5 border-b bg-muted/30 shrink-0">
        <button
          onClick={() => goToPage(currentPage - 1)}
          disabled={currentPage <= 1}
          className="px-2 py-0.5 text-xs rounded hover:bg-muted disabled:opacity-30"
          title="이전 페이지"
        >
          ◀
        </button>
        <div className="flex items-center gap-1">
          <input
            type="number"
            min={1}
            max={numPages}
            value={currentPage}
            onChange={(e) => goToPage(Number(e.target.value))}
            className="w-12 text-center text-xs border rounded px-1 py-0.5 bg-background"
          />
          <span className="text-xs text-muted-foreground">/ {numPages || "..."}</span>
        </div>
        <button
          onClick={() => goToPage(currentPage + 1)}
          disabled={currentPage >= numPages}
          className="px-2 py-0.5 text-xs rounded hover:bg-muted disabled:opacity-30"
          title="다음 페이지"
        >
          ▶
        </button>

        <div className="w-px h-4 bg-border mx-1" />

        <button
          onClick={zoomOut}
          disabled={scaleIdx <= 0}
          className="px-2 py-0.5 text-xs rounded hover:bg-muted disabled:opacity-30"
          title="축소"
        >
          −
        </button>
        <span className="text-xs text-muted-foreground min-w-[40px] text-center">
          {Math.round(scale * 100)}%
        </span>
        <button
          onClick={zoomIn}
          disabled={scaleIdx >= SCALES.length - 1}
          className="px-2 py-0.5 text-xs rounded hover:bg-muted disabled:opacity-30"
          title="확대"
        >
          +
        </button>

        {/* Page group pagination for 50+ page docs */}
        {totalGroups > 1 && (
          <>
            <div className="w-px h-4 bg-border mx-1" />
            <button
              onClick={() => {
                const g = Math.max(0, pageGroup - 1);
                setPageGroup(g);
                setCurrentPage(g * PAGE_GROUP_SIZE + 1);
              }}
              disabled={pageGroup <= 0}
              className="px-1.5 py-0.5 text-xs rounded hover:bg-muted disabled:opacity-30"
            >
              ◁
            </button>
            <span className="text-xs text-muted-foreground">
              {groupStart}–{groupEnd}
            </span>
            <button
              onClick={() => {
                const g = Math.min(totalGroups - 1, pageGroup + 1);
                setPageGroup(g);
                setCurrentPage(g * PAGE_GROUP_SIZE + 1);
              }}
              disabled={pageGroup >= totalGroups - 1}
              className="px-1.5 py-0.5 text-xs rounded hover:bg-muted disabled:opacity-30"
            >
              ▷
            </button>
          </>
        )}

        <div className="flex-1" />
        <span className="text-xs text-muted-foreground truncate max-w-[200px]">
          {filePath}
        </span>
      </div>

      {/* PDF content */}
      <div className="flex-1 overflow-auto flex justify-center bg-muted/20 p-4">
        {error ? (
          <div className="flex items-center justify-center h-full text-destructive">
            <p className="text-sm">PDF 로드 실패: {error}</p>
          </div>
        ) : (
          <Document
            file={src}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            loading={
              <div className="flex items-center justify-center h-32">
                <p className="text-sm text-muted-foreground">PDF 로딩 중...</p>
              </div>
            }
          >
            {loading ? null : (
              <Page
                pageNumber={currentPage}
                scale={scale}
                className="shadow-lg"
                loading={
                  <div className="flex items-center justify-center h-32">
                    <p className="text-xs text-muted-foreground">페이지 렌더링 중...</p>
                  </div>
                }
              />
            )}
          </Document>
        )}
      </div>
    </div>
  );
}
