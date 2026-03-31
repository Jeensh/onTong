"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import * as XLSX from "xlsx";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import { toast } from "sonner";

interface SpreadsheetViewerProps {
  filePath: string;
  tabId: string;
}

type CellData = (string | number | null)[][];

export function SpreadsheetViewer({ filePath, tabId }: SpreadsheetViewerProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<CellData>([]);
  const [sheetNames, setSheetNames] = useState<string[]>([]);
  const [activeSheet, setActiveSheet] = useState(0);
  const [saving, setSaving] = useState(false);
  const [editCell, setEditCell] = useState<{ r: number; c: number } | null>(null);
  const [editValue, setEditValue] = useState("");
  const workbookRef = useRef<XLSX.WorkBook | null>(null);
  const dataRef = useRef<CellData>([]);
  const activeSheetRef = useRef(0);
  const setDirty = useWorkspaceStore((s) => s.setDirty);

  // Keep refs in sync with state so handleSave always reads the latest values
  dataRef.current = data;
  activeSheetRef.current = activeSheet;

  // Load workbook
  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/files/${encodeURIComponent(filePath)}`, {
          cache: "no-store",
        });
        if (!res.ok) throw new Error(`Failed to load: ${res.status}`);
        const buf = await res.arrayBuffer();
        const wb = XLSX.read(buf, { type: "array" });
        if (cancelled) return;
        workbookRef.current = wb;
        setSheetNames(wb.SheetNames);
        setActiveSheet(0);
        loadSheet(wb, 0);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [filePath]);

  function loadSheet(wb: XLSX.WorkBook, idx: number) {
    const ws = wb.Sheets[wb.SheetNames[idx]];
    const json = XLSX.utils.sheet_to_json<(string | number | null)[]>(ws, {
      header: 1,
      defval: null,
    });
    setData(json);
  }

  function handleSheetChange(idx: number) {
    if (!workbookRef.current) return;
    // Sync current sheet data back to workbook before switching
    const wb = workbookRef.current;
    wb.Sheets[wb.SheetNames[activeSheet]] = XLSX.utils.aoa_to_sheet(data);
    setActiveSheet(idx);
    loadSheet(wb, idx);
    setEditCell(null);
  }

  function startEdit(r: number, c: number) {
    setEditCell({ r, c });
    setEditValue(String(data[r]?.[c] ?? ""));
  }

  function commitEdit() {
    if (!editCell || !workbookRef.current) return;
    const { r, c } = editCell;

    // Update local data
    const newData = data.map((row) => [...row]);
    while (newData.length <= r) newData.push([]);
    while (newData[r].length <= c) newData[r].push(null);
    newData[r][c] = editValue === "" ? null : editValue;
    setData(newData);
    // Immediately update the ref so handleSave can read it
    dataRef.current = newData;

    setEditCell(null);
    setDirty(tabId, true);
  }

  // Save handler — uses refs to always get the latest data
  const handleSave = useCallback(async () => {
    if (!workbookRef.current || saving) return;
    setSaving(true);
    try {
      // Rebuild the active sheet from the latest data ref
      const wb = workbookRef.current;
      const sheetIdx = activeSheetRef.current;
      const sheetName = wb.SheetNames[sheetIdx];
      wb.Sheets[sheetName] = XLSX.utils.aoa_to_sheet(dataRef.current);

      const wbOut = XLSX.write(wb, { type: "array", bookType: "xlsx" });
      const u8 = new Uint8Array(wbOut);
      const blob = new Blob([u8], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });
      const form = new FormData();
      const fileName = filePath.split("/").pop() || "file.xlsx";
      form.append("file", blob, fileName);

      const res = await fetch(`/api/files/${encodeURIComponent(filePath)}`, {
        method: "PUT",
        body: form,
      });
      if (!res.ok) throw new Error(`Save failed: ${res.status}`);

      // Reload workbook from the saved blob to keep in sync
      const savedBuf = await blob.arrayBuffer();
      const reloaded = XLSX.read(savedBuf, { type: "array" });
      workbookRef.current = reloaded;
      setSheetNames(reloaded.SheetNames);
      loadSheet(reloaded, sheetIdx);

      setDirty(tabId, false);
      toast.success("저장 완료");
    } catch (e) {
      toast.error("저장 실패: " + (e instanceof Error ? e.message : String(e)));
    } finally {
      setSaving(false);
    }
  }, [filePath, tabId, setDirty, saving]);

  // Ctrl+S
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        handleSave();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleSave]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        <div className="text-sm">불러오는 중...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-destructive">
        <div className="text-sm">로드 실패: {error}</div>
      </div>
    );
  }

  // Determine max columns
  const maxCols = data.reduce((max, row) => Math.max(max, row.length), 0);

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-1.5 border-b bg-muted/30">
        {/* Sheet tabs */}
        <div className="flex gap-1">
          {sheetNames.map((name, i) => (
            <button
              key={name}
              onClick={() => handleSheetChange(i)}
              className={`px-2 py-0.5 text-xs rounded ${
                i === activeSheet
                  ? "bg-primary text-primary-foreground"
                  : "hover:bg-muted"
              }`}
            >
              {name}
            </button>
          ))}
        </div>
        <div className="flex-1" />
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-3 py-1 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {saving ? "저장 중..." : "저장"}
        </button>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="border-collapse text-sm">
          <thead>
            <tr>
              <th className="sticky top-0 left-0 z-20 bg-muted border border-border px-2 py-1 text-xs text-muted-foreground w-10">
                #
              </th>
              {Array.from({ length: maxCols }, (_, c) => (
                <th
                  key={c}
                  className="sticky top-0 z-10 bg-muted border border-border px-2 py-1 text-xs text-muted-foreground min-w-[80px]"
                >
                  {XLSX.utils.encode_col(c)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, r) => (
              <tr key={r}>
                <td className="sticky left-0 z-10 bg-muted border border-border px-2 py-1 text-xs text-muted-foreground text-center">
                  {r + 1}
                </td>
                {Array.from({ length: maxCols }, (_, c) => {
                  const isEditing = editCell?.r === r && editCell?.c === c;
                  const val = row[c];
                  return (
                    <td
                      key={c}
                      className="border border-border px-2 py-1 cursor-cell"
                      onDoubleClick={() => startEdit(r, c)}
                    >
                      {isEditing ? (
                        <input
                          className="w-full bg-transparent outline-none text-sm"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          onBlur={commitEdit}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") commitEdit();
                            if (e.key === "Escape") setEditCell(null);
                          }}
                          autoFocus
                        />
                      ) : (
                        <span className="text-sm">
                          {val !== null && val !== undefined ? String(val) : ""}
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
