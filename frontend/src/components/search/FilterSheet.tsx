"use client";

import { useEffect, useMemo, useState } from "react";
import { X, Check, Filter, Bookmark, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  useSearchStore,
  type FilterSpec,
  type TagFilter,
} from "@/lib/search/useSearchStore";
import {
  loadPresets,
  savePreset,
  deletePreset,
  type FilterPreset,
} from "@/lib/search/filterPresets";

const DOC_TYPES = ["sop", "spec", "decision", "incident", "meeting", "postmortem"];
const STATUSES = ["active", "review", "draft", "deprecated"];
const MTIME_PRESETS: Array<{ key: string; label: string; daysAgo: number | null }> = [
  { key: "all", label: "전체", daysAgo: null },
  { key: "7", label: "최근 7일", daysAgo: 7 },
  { key: "30", label: "최근 30일", daysAgo: 30 },
  { key: "90", label: "최근 90일", daysAgo: 90 },
];

function daysAgoISO(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function ChipList({
  items,
  onRemove,
  tone = "default",
}: {
  items: string[];
  onRemove: (v: string) => void;
  tone?: "default" | "destructive";
}) {
  if (!items.length) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((v) => (
        <Badge
          key={v}
          variant={tone === "destructive" ? "destructive" : "secondary"}
          className="gap-1 pr-1"
        >
          {v}
          <button
            type="button"
            aria-label={`${v} 제거`}
            className="rounded-full hover:bg-black/10 p-0.5"
            onClick={() => onRemove(v)}
          >
            <X className="h-3 w-3" />
          </button>
        </Badge>
      ))}
    </div>
  );
}

export function FilterSheet() {
  const { filterSheetOpen, setFilterSheetOpen, filters, mergeFilters, clearFilters } =
    useSearchStore();

  // Local draft so Apply is explicit
  const [draft, setDraft] = useState<FilterSpec>(filters);
  useEffect(() => {
    if (filterSheetOpen) setDraft(filters);
  }, [filterSheetOpen, filters]);

  const [folderInput, setFolderInput] = useState("");
  const [authorInput, setAuthorInput] = useState("");
  const [tagIncludeInput, setTagIncludeInput] = useState("");
  const [tagExcludeInput, setTagExcludeInput] = useState("");
  const [mtimePreset, setMtimePreset] = useState<string>(() => {
    if (!filters.mtime_from) return "all";
    const d = (new Date().getTime() - new Date(filters.mtime_from).getTime()) / 86400000;
    if (Math.abs(d - 7) < 1) return "7";
    if (Math.abs(d - 30) < 1) return "30";
    if (Math.abs(d - 90) < 1) return "90";
    return "custom";
  });

  // Folders
  const folders = draft.folders ?? [];
  const addFolder = () => {
    const v = folderInput.trim();
    if (!v) return;
    if (folders.includes(v)) {
      setFolderInput("");
      return;
    }
    setDraft({ ...draft, folders: [...folders, v] });
    setFolderInput("");
  };
  const removeFolder = (v: string) =>
    setDraft({ ...draft, folders: folders.filter((f) => f !== v) });

  // Authors
  const authors = draft.authors ?? [];
  const addAuthor = () => {
    const raw = authorInput.trim();
    if (!raw) return;
    const v = raw.startsWith("@") ? raw : `@${raw}`;
    if (authors.includes(v)) {
      setAuthorInput("");
      return;
    }
    setDraft({ ...draft, authors: [...authors, v] });
    setAuthorInput("");
  };
  const removeAuthor = (v: string) =>
    setDraft({ ...draft, authors: authors.filter((a) => a !== v) });

  // Tags
  const tags: TagFilter = draft.tags ?? {};
  const tagInclude = tags.include ?? [];
  const tagExclude = tags.exclude ?? [];
  const tagMode: "AND" | "OR" = tags.mode ?? "OR";
  const addTagInclude = () => {
    const v = tagIncludeInput.trim();
    if (!v || tagInclude.includes(v)) {
      setTagIncludeInput("");
      return;
    }
    setDraft({
      ...draft,
      tags: { ...tags, include: [...tagInclude, v] },
    });
    setTagIncludeInput("");
  };
  const removeTagInclude = (v: string) =>
    setDraft({
      ...draft,
      tags: { ...tags, include: tagInclude.filter((t) => t !== v) },
    });
  const addTagExclude = () => {
    const v = tagExcludeInput.trim();
    if (!v || tagExclude.includes(v)) {
      setTagExcludeInput("");
      return;
    }
    setDraft({
      ...draft,
      tags: { ...tags, exclude: [...tagExclude, v] },
    });
    setTagExcludeInput("");
  };
  const removeTagExclude = (v: string) =>
    setDraft({
      ...draft,
      tags: { ...tags, exclude: tagExclude.filter((t) => t !== v) },
    });
  const setTagMode = (m: "AND" | "OR") =>
    setDraft({ ...draft, tags: { ...tags, mode: m } });

  // Types
  const types = draft.types ?? [];
  const toggleType = (t: string) => {
    const next = types.includes(t) ? types.filter((x) => x !== t) : [...types, t];
    setDraft({ ...draft, types: next });
  };

  // Statuses
  const statuses = draft.statuses ?? [];
  const toggleStatus = (s: string) => {
    const next = statuses.includes(s)
      ? statuses.filter((x) => x !== s)
      : [...statuses, s];
    setDraft({ ...draft, statuses: next });
  };

  // Mtime preset
  const applyMtimePreset = (key: string) => {
    setMtimePreset(key);
    const preset = MTIME_PRESETS.find((p) => p.key === key);
    if (!preset || preset.daysAgo === null) {
      const next = { ...draft };
      delete next.mtime_from;
      delete next.mtime_to;
      setDraft(next);
    } else {
      setDraft({
        ...draft,
        mtime_from: daysAgoISO(preset.daysAgo),
        mtime_to: undefined,
      });
    }
  };

  // DSL
  const [dslDraft, setDslDraft] = useState(draft.boolean ?? "");
  useEffect(() => setDslDraft(draft.boolean ?? ""), [draft.boolean]);

  // Presets
  const [presets, setPresets] = useState<FilterPreset[]>([]);
  const [presetNameInput, setPresetNameInput] = useState("");
  useEffect(() => {
    if (filterSheetOpen) setPresets(loadPresets());
  }, [filterSheetOpen]);

  const applyPreset = (p: FilterPreset) => {
    setDraft(p.filters);
    setDslDraft(p.filters.boolean ?? "");
    const mf = p.filters.mtime_from;
    if (!mf) {
      setMtimePreset("all");
    } else {
      const d = (new Date().getTime() - new Date(mf).getTime()) / 86400000;
      if (Math.abs(d - 7) < 1) setMtimePreset("7");
      else if (Math.abs(d - 30) < 1) setMtimePreset("30");
      else if (Math.abs(d - 90) < 1) setMtimePreset("90");
      else setMtimePreset("custom");
    }
  };

  const saveCurrentAsPreset = () => {
    const name = presetNameInput.trim();
    if (!name) return;
    const snapshot: FilterSpec = { ...draft, boolean: dslDraft || undefined };
    if (snapshot.tags && !snapshot.tags.include?.length && !snapshot.tags.exclude?.length) {
      delete snapshot.tags;
    }
    try {
      savePreset(name, snapshot);
      setPresets(loadPresets());
      setPresetNameInput("");
    } catch (err) {
      console.warn("preset save failed:", err);
    }
  };

  const removePreset = (id: string) => {
    deletePreset(id);
    setPresets(loadPresets());
  };

  const apply = () => {
    const patch: FilterSpec = { ...draft, boolean: dslDraft || undefined };
    // Clear empty subfields
    if (patch.tags && !patch.tags.include?.length && !patch.tags.exclude?.length) {
      delete patch.tags;
    }
    mergeFilters(patch);
    setFilterSheetOpen(false);
  };

  const resetAll = () => {
    setDraft({});
    setDslDraft("");
    setMtimePreset("all");
    clearFilters();
  };

  useEffect(() => {
    if (!filterSheetOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        setFilterSheetOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [filterSheetOpen, setFilterSheetOpen]);

  const activeCount = useMemo(() => {
    const f = draft;
    let n = 0;
    if (f.folders?.length) n++;
    if (f.tags?.include?.length || f.tags?.exclude?.length) n++;
    if (f.authors?.length) n++;
    if (f.types?.length) n++;
    if (f.mtime_from || f.mtime_to) n++;
    if (f.statuses?.length) n++;
    if (f.boolean) n++;
    return n;
  }, [draft]);

  if (!filterSheetOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[60]"
      role="dialog"
      aria-modal="true"
      aria-label="고급 필터"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/20 supports-backdrop-filter:backdrop-blur-xs"
        onClick={() => setFilterSheetOpen(false)}
      />
      {/* Drawer */}
      <div className="absolute right-0 top-0 h-full w-[380px] max-w-full bg-popover text-popover-foreground ring-1 ring-foreground/10 shadow-xl flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4" />
            <h2 className="font-heading text-sm font-medium">고급 필터</h2>
            {activeCount > 0 && (
              <Badge variant="secondary" className="h-5">
                {activeCount}
              </Badge>
            )}
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="닫기"
            onClick={() => setFilterSheetOpen(false)}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5 text-sm">
          {/* Presets */}
          <section>
            <h3 className="font-medium mb-2 flex items-center gap-1.5">
              <Bookmark className="h-3.5 w-3.5" />
              저장된 프리셋
            </h3>
            {presets.length === 0 ? (
              <p className="text-[11px] text-muted-foreground mb-2">
                자주 쓰는 필터 조합을 이름으로 저장하고 재사용할 수 있습니다.
              </p>
            ) : (
              <div className="flex flex-wrap gap-1 mb-2">
                {presets.map((p) => (
                  <span
                    key={p.id}
                    className="inline-flex items-center gap-1 rounded-md border border-primary/20 bg-primary/5 px-2 py-0.5 text-xs"
                  >
                    <button
                      type="button"
                      onClick={() => applyPreset(p)}
                      className="text-primary hover:underline"
                      title={`${p.name} 적용`}
                    >
                      {p.name}
                    </button>
                    <button
                      type="button"
                      onClick={() => removePreset(p.id)}
                      aria-label={`${p.name} 프리셋 삭제`}
                      className="rounded-full p-0.5 hover:bg-destructive/10 hover:text-destructive"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
            <div className="flex gap-2">
              <Input
                placeholder="프리셋 이름 (예: 내 문서 최근 30일)"
                value={presetNameInput}
                onChange={(e) => setPresetNameInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    saveCurrentAsPreset();
                  }
                }}
                className="h-8 text-xs"
              />
              <Button
                size="sm"
                variant="outline"
                onClick={saveCurrentAsPreset}
                disabled={!presetNameInput.trim()}
              >
                <Save className="h-3.5 w-3.5 mr-1" />
                저장
              </Button>
            </div>
          </section>

          {/* Folders */}
          <section>
            <h3 className="font-medium mb-2">📁 폴더</h3>
            <div className="flex gap-2 mb-2">
              <Input
                placeholder="ERP/마스터데이터"
                value={folderInput}
                onChange={(e) => setFolderInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addFolder();
                  }
                }}
                className="h-8 text-xs"
              />
              <Button size="sm" variant="outline" onClick={addFolder}>
                추가
              </Button>
            </div>
            <ChipList items={folders} onRemove={removeFolder} />
          </section>

          {/* Tags */}
          <section>
            <h3 className="font-medium mb-2">🏷️ 태그</h3>
            <div className="flex items-center gap-2 mb-2 text-xs text-muted-foreground">
              <span>모드:</span>
              <button
                type="button"
                className={`rounded px-2 py-0.5 text-xs ${
                  tagMode === "OR"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted"
                }`}
                onClick={() => setTagMode("OR")}
              >
                OR
              </button>
              <button
                type="button"
                className={`rounded px-2 py-0.5 text-xs ${
                  tagMode === "AND"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted"
                }`}
                onClick={() => setTagMode("AND")}
              >
                AND
              </button>
            </div>
            <div className="space-y-2">
              <div>
                <div className="text-xs text-muted-foreground mb-1">포함</div>
                <div className="flex gap-2 mb-1">
                  <Input
                    placeholder="재고"
                    value={tagIncludeInput}
                    onChange={(e) => setTagIncludeInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addTagInclude();
                      }
                    }}
                    className="h-8 text-xs"
                  />
                  <Button size="sm" variant="outline" onClick={addTagInclude}>
                    추가
                  </Button>
                </div>
                <ChipList items={tagInclude} onRemove={removeTagInclude} />
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">제외</div>
                <div className="flex gap-2 mb-1">
                  <Input
                    placeholder="draft"
                    value={tagExcludeInput}
                    onChange={(e) => setTagExcludeInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addTagExclude();
                      }
                    }}
                    className="h-8 text-xs"
                  />
                  <Button size="sm" variant="outline" onClick={addTagExclude}>
                    추가
                  </Button>
                </div>
                <ChipList
                  items={tagExclude}
                  onRemove={removeTagExclude}
                  tone="destructive"
                />
              </div>
            </div>
          </section>

          {/* Authors */}
          <section>
            <h3 className="font-medium mb-2">👤 작성자</h3>
            <div className="flex gap-2 mb-2">
              <Input
                placeholder="@동해"
                value={authorInput}
                onChange={(e) => setAuthorInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addAuthor();
                  }
                }}
                className="h-8 text-xs"
              />
              <Button size="sm" variant="outline" onClick={addAuthor}>
                추가
              </Button>
            </div>
            <ChipList items={authors} onRemove={removeAuthor} />
          </section>

          {/* Doc types */}
          <section>
            <h3 className="font-medium mb-2">📄 문서 유형</h3>
            <div className="flex flex-wrap gap-1">
              {DOC_TYPES.map((t) => {
                const on = types.includes(t);
                return (
                  <button
                    key={t}
                    type="button"
                    onClick={() => toggleType(t)}
                    className={`rounded-full px-2.5 py-0.5 text-xs transition ${
                      on
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground hover:bg-muted/80"
                    }`}
                  >
                    {on && <Check className="inline h-3 w-3 mr-0.5" />}
                    {t}
                  </button>
                );
              })}
            </div>
          </section>

          {/* Mtime */}
          <section>
            <h3 className="font-medium mb-2">📅 수정일</h3>
            <div className="flex flex-wrap gap-1 mb-2">
              {MTIME_PRESETS.map((p) => {
                const on = mtimePreset === p.key;
                return (
                  <button
                    key={p.key}
                    type="button"
                    onClick={() => applyMtimePreset(p.key)}
                    className={`rounded-full px-2.5 py-0.5 text-xs transition ${
                      on
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground hover:bg-muted/80"
                    }`}
                  >
                    {p.label}
                  </button>
                );
              })}
            </div>
            <div className="flex gap-2">
              <Input
                type="date"
                value={draft.mtime_from ?? ""}
                onChange={(e) => {
                  setMtimePreset("custom");
                  setDraft({ ...draft, mtime_from: e.target.value || undefined });
                }}
                className="h-8 text-xs"
              />
              <span className="text-xs text-muted-foreground self-center">~</span>
              <Input
                type="date"
                value={draft.mtime_to ?? ""}
                onChange={(e) => {
                  setMtimePreset("custom");
                  setDraft({ ...draft, mtime_to: e.target.value || undefined });
                }}
                className="h-8 text-xs"
              />
            </div>
          </section>

          {/* Statuses */}
          <section>
            <h3 className="font-medium mb-2">🚦 상태</h3>
            <div className="flex flex-wrap gap-1">
              {STATUSES.map((s) => {
                const on = statuses.includes(s);
                return (
                  <button
                    key={s}
                    type="button"
                    onClick={() => toggleStatus(s)}
                    className={`rounded-full px-2.5 py-0.5 text-xs transition ${
                      on
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground hover:bg-muted/80"
                    }`}
                  >
                    {s}
                  </button>
                );
              })}
            </div>
            <p className="text-[10px] text-muted-foreground mt-1">
              기본적으로 deprecated는 제외됩니다. 명시적으로 선택하면 포함됩니다.
            </p>
          </section>

          {/* Boolean DSL */}
          <section>
            <h3 className="font-medium mb-2">⚡ Boolean DSL (고급)</h3>
            <Input
              placeholder="(tag:재고 OR tag:주문) AND author:@동해"
              value={dslDraft}
              onChange={(e) => setDslDraft(e.target.value)}
              className="h-8 text-xs font-mono"
            />
            <p className="text-[10px] text-muted-foreground mt-1">
              설정 시 위 필드보다 우선합니다. AND/OR/NOT/괄호 지원.
            </p>
          </section>
        </div>

        <div className="flex items-center justify-between gap-2 px-4 py-3 border-t bg-muted/50">
          <Button variant="ghost" size="sm" onClick={resetAll}>
            필터 초기화
          </Button>
          <Button size="sm" onClick={apply}>
            <Check className="h-3.5 w-3.5 mr-1" />
            적용 ({activeCount})
          </Button>
        </div>
      </div>
    </div>
  );
}
