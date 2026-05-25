"use client";

/**
 * Perspective dropdown (R4-T3.4) — toolbar 한 칸. 저장된 view 목록 + 적용 + 새로 저장.
 *
 * Saved Perspective 클릭 → spec 적용 (mode/focus/target/n_max + activePerspectiveId).
 * "현 view 저장" 클릭 → prompt 로 이름 받아 createPerspective.
 * Active perspective 가 있으면 "x" 로 해제 (ad-hoc 으로 돌아감).
 */
import { useEffect, useState } from "react";
import { Bookmark, BookmarkPlus, ChevronDown, Loader2, Trash2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { ontologyApi, type PerspectiveDTO } from "@/lib/api/ontology";
import { useWorkbench } from "./store";

interface Props {
  repoId: string;
}

export function PerspectiveDropdown({ repoId }: Props) {
  const [open, setOpen] = useState(false);
  const [list, setList] = useState<PerspectiveDTO[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  const activeId = useWorkbench((s) => s.activePerspectiveId);
  const setActiveId = useWorkbench((s) => s.setActivePerspectiveId);
  const applyGraphState = useWorkbench((s) => s.applyGraphState);
  // 현재 graph state (저장 시 spec 빌드용)
  const mode = useWorkbench((s) => s.graphMode);
  const focus = useWorkbench((s) => s.graphFocus);
  const target = useWorkbench((s) => s.graphTarget);
  const nMax = useWorkbench((s) => s.graphNMax);

  const reload = async () => {
    setLoading(true);
    try {
      const items = await ontologyApi.listPerspectives(repoId);
      setList(items);
    } catch {
      setList([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // mount + activeId 변경 시 list 로드 (active name 표시 위해)
    if (open || activeId !== null) void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, repoId, activeId]);

  // 외부 클릭 닫기
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      const t = e.target as HTMLElement;
      if (!t.closest("[data-pdrop]")) setOpen(false);
    };
    window.addEventListener("click", onClick);
    return () => window.removeEventListener("click", onClick);
  }, [open]);

  const apply = (p: PerspectiveDTO) => {
    applyGraphState({
      mode: p.spec.mode,
      focus: p.spec.focus_fqn ?? null,
      target: p.spec.target_fqn ?? null,
      nMax: p.spec.n_max,
    });
    setActiveId(p.id);
    setOpen(false);
  };

  const saveCurrent = async () => {
    const name = window.prompt("이 view 의 이름을 입력하세요");
    if (!name?.trim()) return;
    setBusy(true);
    try {
      const created = await ontologyApi.createPerspective(repoId, {
        name: name.trim(),
        spec: {
          mode, n_max: nMax,
          focus_fqn: focus, target_fqn: target,
          hops: null,
          visible_kinds: ["term", "code_type", "action", "domain"],
          visible_edge_kinds: [
            "extends", "implements", "composition",
            "type_realization_primary", "type_realization_partial",
            "realization", "contains",
          ],
          compound: false,
          filter: {},
          lens: null,
        },
      });
      setActiveId(created.id);
      await reload();
    } catch (e) {
      alert(`저장 실패: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (p: PerspectiveDTO) => {
    if (!confirm(`"${p.name}" 삭제하시겠습니까?`)) return;
    setBusy(true);
    try {
      await ontologyApi.deletePerspective(repoId, p.id);
      if (activeId === p.id) setActiveId(null);
      await reload();
    } finally {
      setBusy(false);
    }
  };

  const activeName = list.find((p) => p.id === activeId)?.name;

  return (
    <div className="relative" data-pdrop>
      <div className="flex items-center gap-1">
        <button
          onClick={() => setOpen((v) => !v)}
          className={cn(
            "flex items-center gap-1 px-2 py-0.5 rounded border text-[11px] transition",
            activeId !== null
              ? "bg-violet-500/15 border-violet-500/40 text-violet-300"
              : "bg-muted border-border text-muted-foreground hover:text-foreground",
          )}
          title="저장된 view (perspective)"
        >
          <Bookmark className="w-3 h-3" />
          <span className="max-w-[140px] truncate">
            {activeName ?? "View"}
          </span>
          <ChevronDown className="w-3 h-3" />
        </button>
        {activeId !== null && (
          <button
            onClick={() => setActiveId(null)}
            title="현재 view 해제 (ad-hoc 모드)"
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="w-3 h-3" />
          </button>
        )}
      </div>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-72 bg-card border border-border rounded shadow-2xl z-30 text-[12px]">
          <div className="px-3 py-2 border-b border-border flex items-center justify-between">
            <span className="text-muted-foreground text-[10px] uppercase tracking-wider">
              저장된 view
            </span>
            <button
              onClick={saveCurrent}
              disabled={busy}
              className="flex items-center gap-1 text-[11px] text-primary hover:text-primary/80"
              title="현재 view (mode/focus/n_max) 저장"
            >
              {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <BookmarkPlus className="w-3 h-3" />}
              현 view 저장
            </button>
          </div>
          <div className="max-h-72 overflow-y-auto">
            {loading ? (
              <div className="p-4 flex justify-center"><Loader2 className="w-3 h-3 animate-spin" /></div>
            ) : list.length === 0 ? (
              <div className="p-4 text-center text-muted-foreground text-[11px]">
                저장된 view 없음 — 「현 view 저장」 으로 추가
              </div>
            ) : (
              list.map((p) => (
                <div
                  key={p.id}
                  className={cn(
                    "px-3 py-2 border-b border-border last:border-b-0 hover:bg-muted/40 group flex items-center gap-2",
                    activeId === p.id && "bg-violet-500/10",
                  )}
                >
                  <button
                    onClick={() => apply(p)}
                    className="flex-1 text-left"
                  >
                    <div className="font-medium truncate">{p.name}</div>
                    <div className="text-[10px] text-muted-foreground truncate">
                      {p.spec.mode}
                      {p.spec.focus_fqn && ` · focus=${p.spec.focus_fqn.split(".").slice(-2).join(".")}`}
                      {p.spec.n_max !== 60 && ` · n=${p.spec.n_max}`}
                    </div>
                  </button>
                  <button
                    onClick={() => remove(p)}
                    title="삭제"
                    className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
