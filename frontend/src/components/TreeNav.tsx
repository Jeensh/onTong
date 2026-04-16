"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ChevronRight,
  ChevronDown,
  File,
  Folder,
  FolderOpen,
  FolderPlus,
  FilePlus,
  Trash2,
  RefreshCw,
  Pencil,
  ImageOff,
  Loader2,
  FolderTree,
  Tags,
  Settings,
  AlertTriangle,
  Search,
  Network,
  Link,
  Shield,
  Zap,
  Plus,
  X,
  Gauge,
  ClipboardList,
  Lock,
  Users,
  Share2,
  Info,
} from "lucide-react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
  useDraggable,
  type DragEndEvent,
} from "@dnd-kit/core";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import { useSearchStore } from "@/lib/search/useSearchStore";
import { toast } from "sonner";
import type { WikiTreeNode, SkillMeta, SkillListResponse } from "@/types";
import { fetchSkills, createSkill, deleteSkill, toggleSkill, fetchSkillContext, moveSkill } from "@/lib/api/skills";
import { SkillCreateDialog } from "@/components/skills/SkillCreateDialog";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Eye, EyeOff, Copy, Pin, GripVertical } from "lucide-react";
import { fetchSubtree } from "@/lib/api/wiki";
import { ContextMenu as ACLContextMenu, type MenuItemDef } from "@/components/ContextMenu";
import { ShareDialog } from "@/components/ShareDialog";
import { PropertiesPanel } from "@/components/PropertiesPanel";
import { useAuth } from "@/hooks/useAuth";

// ── API helpers ───────────────────────────────────────────────────────

async function apiMove(oldPath: string, newPath: string, isDir: boolean) {
  const endpoint = isDir
    ? `/api/wiki/folder/${encodeURIComponent(oldPath)}`
    : `/api/wiki/file/${encodeURIComponent(oldPath)}`;
  const res = await fetch(endpoint, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ new_path: newPath }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
}

// ── Context Menu ─────────────────────────────────────────────────────

interface ContextMenuState {
  x: number;
  y: number;
  node: WikiTreeNode | null; // null = empty space (root)
}

function copyDocLink(path: string) {
  if (path.endsWith(".md")) {
    const stem = path.split("/").pop()?.replace(".md", "") ?? path;
    navigator.clipboard.writeText(`[[${stem}]]`);
    toast.success("문서 링크 복사됨: [[" + stem + "]]");
  } else {
    navigator.clipboard.writeText(path);
    toast.success("경로 복사됨");
  }
}

function ContextMenu({
  state,
  onClose,
  onRename,
  onDeleteFile,
  onDeleteFolder,
  onNewFileInFolder,
  onNewSubfolder,
  onCreateNewVersion,
  statusMap,
}: {
  state: ContextMenuState;
  onClose: () => void;
  onRename: (node: WikiTreeNode) => void;
  onDeleteFile: (path: string) => void;
  onDeleteFolder: (path: string) => void;
  onNewFileInFolder: (folderPath: string) => void;
  onNewSubfolder: (folderPath: string) => void;
  onCreateNewVersion?: (path: string) => void;
  statusMap?: Record<string, string>;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  const isRoot = state.node === null;
  const isDir = state.node?.is_dir ?? false;

  return (
    <div
      ref={ref}
      className="fixed z-50 min-w-[160px] rounded-md border bg-popover p-1 shadow-md text-sm"
      style={{ left: state.x, top: state.y }}
    >
      {/* Root empty space or folder: show create options */}
      {(isRoot || isDir) && (
        <>
          <button
            onClick={() => { onNewFileInFolder(isRoot ? "__root__" : state.node!.path); onClose(); }}
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 hover:bg-muted"
          >
            <FilePlus className="h-3.5 w-3.5" /> 새 문서
          </button>
          <button
            onClick={() => { onNewSubfolder(isRoot ? "__root__" : state.node!.path); onClose(); }}
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 hover:bg-muted"
          >
            <FolderPlus className="h-3.5 w-3.5" /> 새 폴더
          </button>
        </>
      )}
      {/* Node-specific actions (copy, rename, delete) */}
      {!isRoot && (
        <>
          <div className="my-1 border-t" />
          <button
            onClick={() => { copyDocLink(state.node!.path); onClose(); }}
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 hover:bg-muted"
          >
            <Link className="h-3.5 w-3.5" /> 문서 링크 복사
          </button>
          {!isDir && state.node!.path.endsWith(".md") && onCreateNewVersion && statusMap?.[state.node!.path] !== "deprecated" && (
            <button
              onClick={() => { onCreateNewVersion(state.node!.path); onClose(); }}
              className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 hover:bg-muted"
            >
              <Copy className="h-3.5 w-3.5" /> 새 버전 만들기
            </button>
          )}
          <div className="my-1 border-t" />
          <button
            onClick={() => { onRename(state.node!); onClose(); }}
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 hover:bg-muted"
          >
            <Pencil className="h-3.5 w-3.5" /> 이름 변경
          </button>
          <div className="my-1 border-t" />
          {isDir ? (
            <button
              onClick={() => { onDeleteFolder(state.node!.path); onClose(); }}
              className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-destructive hover:bg-destructive/10"
            >
              <Trash2 className="h-3.5 w-3.5" /> 폴더 삭제
            </button>
          ) : (
            <button
              onClick={() => { onDeleteFile(state.node!.path); onClose(); }}
              className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-destructive hover:bg-destructive/10"
            >
              <Trash2 className="h-3.5 w-3.5" /> 삭제
            </button>
          )}
        </>
      )}
    </div>
  );
}

// ── Inline Name Input ────────────────────────────────────────────────

function InlineInput({
  defaultValue,
  icon: Icon,
  placeholder,
  indent,
  onSubmit,
  onCancel,
}: {
  defaultValue?: string;
  icon: typeof File;
  placeholder: string;
  indent: number;
  onSubmit: (name: string) => void;
  onCancel: () => void;
}) {
  const [value, setValue] = useState(defaultValue ?? "");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    // Select filename without extension on rename
    if (defaultValue) {
      const dotIndex = defaultValue.lastIndexOf(".");
      inputRef.current?.setSelectionRange(0, dotIndex > 0 ? dotIndex : defaultValue.length);
    }
  }, [defaultValue]);

  const handleSubmit = () => {
    const name = value.trim();
    if (!name) { onCancel(); return; }
    onSubmit(name);
  };

  return (
    <div className="flex items-center gap-1 py-0.5" style={{ paddingLeft: `${indent}px` }}>
      <Icon className="h-3.5 w-3.5 shrink-0 text-primary" />
      <input
        ref={inputRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.nativeEvent.isComposing) return;
          if (e.key === "Enter") handleSubmit();
          if (e.key === "Escape") onCancel();
        }}
        onBlur={handleSubmit}
        className="flex-1 text-sm bg-transparent border-b border-primary/50 outline-none px-1 py-0.5 min-w-0"
        placeholder={placeholder}
      />
    </div>
  );
}

// ── Draggable Tree Item ───────────────────────────────────────────────

function DraggableTreeItem({
  node,
  depth,
  renamingPath,
  activeFilePath,
  onRenameSubmit,
  onRenameCancel,
  onContextMenu,
  onOpenTab,
  creatingIn,
  creatingType,
  onCreateSubmit,
  onCreateCancel,
  onLoadChildren,
  statusMap,
}: {
  node: WikiTreeNode;
  depth: number;
  renamingPath: string | null;
  activeFilePath: string | null;
  onRenameSubmit: (node: WikiTreeNode, newName: string) => void;
  onRenameCancel: () => void;
  onContextMenu: (e: React.MouseEvent, node: WikiTreeNode) => void;
  onOpenTab: (path: string) => void;
  creatingIn: string | null;
  creatingType: "file" | "folder" | null;
  onCreateSubmit: (name: string) => void;
  onCreateCancel: () => void;
  onLoadChildren: (path: string) => Promise<void>;
  statusMap?: Record<string, string>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [childLoading, setChildLoading] = useState(false);
  const indent = depth * 12 + 8;

  // Check if this folder needs lazy loading (has_children but no loaded children)
  const needsLazyLoad = node.is_dir && node.has_children && node.children.length === 0;

  const handleExpand = useCallback(async () => {
    if (expanded) {
      setExpanded(false);
      return;
    }
    if (needsLazyLoad) {
      setChildLoading(true);
      try {
        await onLoadChildren(node.path);
      } finally {
        setChildLoading(false);
      }
    }
    setExpanded(true);
  }, [expanded, needsLazyLoad, onLoadChildren, node.path]);

  // Auto-expand folder when it contains the active file
  useEffect(() => {
    if (node.is_dir && activeFilePath?.startsWith(node.path + "/")) {
      if (needsLazyLoad) {
        onLoadChildren(node.path).then(() => setExpanded(true));
      } else {
        setExpanded(true);
      }
    }
  }, [activeFilePath, node.is_dir, node.path, needsLazyLoad, onLoadChildren]);

  const { attributes, listeners, setNodeRef: setDragRef, isDragging } = useDraggable({
    id: node.path,
    data: { node },
  });

  const { setNodeRef: setDropRef, isOver } = useDroppable({
    id: `drop:${node.path}`,
    disabled: !node.is_dir,
    data: { folderPath: node.path },
  });

  // Auto-expand when something is dragged over or creating inside
  useEffect(() => {
    if ((isOver || creatingIn === node.path) && !expanded) setExpanded(true);
  }, [isOver, creatingIn, node.path, expanded]);

  const isRenaming = renamingPath === node.path;

  if (node.is_dir) {
    return (
      <div ref={setDropRef}>
        {/* Folder row */}
        {isRenaming ? (
          <InlineInput
            icon={Folder}
            defaultValue={node.name}
            placeholder="폴더명"
            indent={indent}
            onSubmit={(name) => onRenameSubmit(node, name)}
            onCancel={onRenameCancel}
          />
        ) : (
          <div
            ref={setDragRef}
            {...listeners}
            {...attributes}
            onContextMenu={(e) => onContextMenu(e, node)}
            onClick={() => handleExpand()}
            className={`flex items-center gap-1 w-full px-2 py-1 text-sm rounded-sm cursor-pointer select-none
              hover:bg-muted/50 ${isDragging ? "opacity-40" : ""} ${isOver ? "bg-primary/10" : ""}`}
            style={{ paddingLeft: `${indent}px` }}
          >
            {childLoading ? (
              <Loader2 className="h-3.5 w-3.5 shrink-0 text-muted-foreground animate-spin" />
            ) : expanded ? (
              <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            )}
            {expanded
              ? <FolderOpen className={`h-3.5 w-3.5 shrink-0 ${node.name.startsWith("@") ? "text-emerald-500" : node.name.startsWith("_") ? "text-muted-foreground/50" : "text-primary/70"}`} />
              : <Folder className={`h-3.5 w-3.5 shrink-0 ${node.name.startsWith("@") ? "text-emerald-500" : node.name.startsWith("_") ? "text-muted-foreground/50" : "text-primary/70"}`} />
            }
            <span className={`truncate flex-1 ${node.name.startsWith("_") ? "text-muted-foreground" : ""}`}>{node.name}</span>
            {node.my_permission === "read" && (
              <span title="읽기 전용"><Lock className="h-3 w-3 shrink-0 text-muted-foreground/60 ml-1" /></span>
            )}
            {node.shared && (
              <span title="공유됨"><Users className="h-3 w-3 shrink-0 text-primary/60 ml-1" /></span>
            )}
          </div>
        )}

        {/* Children */}
        {expanded && (
          <div>
            {creatingIn === node.path && creatingType === "folder" && (
              <InlineInput icon={Folder} placeholder="폴더명" indent={indent + 20}
                onSubmit={onCreateSubmit} onCancel={onCreateCancel} />
            )}
            {creatingIn === node.path && creatingType === "file" && (
              <InlineInput icon={File} placeholder="파일명.md" indent={indent + 20}
                onSubmit={onCreateSubmit} onCancel={onCreateCancel} />
            )}
            {node.children.map((child) => (
              <DraggableTreeItem key={child.path} node={child} depth={depth + 1}
                renamingPath={renamingPath} activeFilePath={activeFilePath}
                onRenameSubmit={onRenameSubmit} onRenameCancel={onRenameCancel}
                onContextMenu={onContextMenu} onOpenTab={onOpenTab}
                creatingIn={creatingIn} creatingType={creatingType}
                onCreateSubmit={onCreateSubmit} onCreateCancel={onCreateCancel}
                onLoadChildren={onLoadChildren} statusMap={statusMap} />
            ))}
          </div>
        )}
      </div>
    );
  }

  // File row
  return isRenaming ? (
    <InlineInput
      icon={File}
      defaultValue={node.name}
      placeholder="파일명.md"
      indent={indent + 14}
      onSubmit={(name) => onRenameSubmit(node, name)}
      onCancel={onRenameCancel}
    />
  ) : (
    <div
      ref={setDragRef}
      {...listeners}
      {...attributes}
      onContextMenu={(e) => onContextMenu(e, node)}
      onClick={() => onOpenTab(node.path)}
      className={`flex items-center gap-1 w-full px-2 py-1 text-sm rounded-sm cursor-pointer select-none
        ${node.path === activeFilePath
          ? "bg-primary/15 text-primary font-medium"
          : "hover:bg-muted/50"
        } ${isDragging ? "opacity-40" : ""}
        ${statusMap?.[node.path] === "deprecated" ? "opacity-50" : ""}`}
      style={{ paddingLeft: `${indent}px` }}
    >
      <span className="w-3.5 shrink-0" />
      <File className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      <span className={`truncate flex-1 ${statusMap?.[node.path] === "deprecated" ? "line-through" : ""}`}>
        {node.name}
      </span>
      {node.my_permission === "read" && (
        <span title="읽기 전용"><Lock className="h-3 w-3 shrink-0 text-muted-foreground/60 ml-1" /></span>
      )}
      {node.shared && (
        <span title="공유됨"><Users className="h-3 w-3 shrink-0 text-primary/60 ml-1" /></span>
      )}
    </div>
  );
}

// ── Root drop zone ────────────────────────────────────────────────────

function RootDropZone({ children, onContextMenu }: { children: React.ReactNode; onContextMenu: (e: React.MouseEvent) => void }) {
  const { setNodeRef, isOver } = useDroppable({ id: "drop:__root__", data: { folderPath: "" } });
  return (
    <div
      ref={setNodeRef}
      className={`flex-1 overflow-auto py-1 min-h-0 ${isOver ? "bg-primary/5" : ""}`}
      onContextMenu={onContextMenu}
    >
      {children}
    </div>
  );
}

// ── TreeNav ──────────────────────────────────────────────────────────

// ── Unused Images Panel ─────────────────────────────────────────────

interface UnusedImage {
  filename: string;
  path: string;
  size: number;
}

// ── Tag Browser Section ──────────────────────────────────────────────

const SIDEBAR_FILE_LIMIT = 20;
const SIDEBAR_TAG_LIMIT = 30;

function TagBrowserSection({ onOpenTab }: { onOpenTab: (path: string) => void }) {
  const [templates, setTemplates] = useState<{ domain_processes: Record<string, string[]>; tag_presets: string[] } | null>(null);
  const [loading, setLoading] = useState(true);

  // Domain tree state
  const [expandedDomain, setExpandedDomain] = useState<string | null>(null);
  const [expandedProcess, setExpandedProcess] = useState<string | null>(null);
  const [processFiles, setProcessFiles] = useState<Record<string, { files: string[]; total: number }>>({});
  const [loadingProcess, setLoadingProcess] = useState<string | null>(null);

  // Tag state — paginated with search
  const [tagSearch, setTagSearch] = useState("");
  const [visibleTags, setVisibleTags] = useState<{ name: string; count: number }[]>([]);
  const [tagTotal, setTagTotal] = useState(0);
  const [tagOffset, setTagOffset] = useState(0);
  const [expandedTag, setExpandedTag] = useState<string | null>(null);
  const [tagFiles, setTagFiles] = useState<{ files: string[]; total: number }>({ files: [], total: 0 });
  const tagSearchTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    fetch("/api/metadata/templates")
      .then((r) => r.json())
      .then((tmpl) => { setTemplates(tmpl); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  // Load tags paginated
  const loadTags = useCallback((query: string, offset: number) => {
    fetch(`/api/metadata/tags/search?q=${encodeURIComponent(query)}&offset=${offset}&limit=${SIDEBAR_TAG_LIMIT}`)
      .then((r) => r.json())
      .then((d) => {
        setVisibleTags(d.tags || []);
        setTagTotal(d.total || 0);
        setTagOffset(offset);
      })
      .catch(() => {});
  }, []);

  useEffect(() => { loadTags("", 0); }, [loadTags]);

  const handleTagSearch = useCallback((q: string) => {
    setTagSearch(q);
    clearTimeout(tagSearchTimer.current);
    tagSearchTimer.current = setTimeout(() => loadTags(q, 0), 200);
  }, [loadTags]);

  const toggleDomain = useCallback((domain: string) => {
    setExpandedDomain((prev) => (prev === domain ? null : domain));
    setExpandedProcess(null);
  }, []);

  const fetchProcessFiles = useCallback((process: string, offset: number) => {
    setLoadingProcess(process);
    fetch(`/api/metadata/files-by-tag?field=process&value=${encodeURIComponent(process)}&offset=${offset}&limit=${SIDEBAR_FILE_LIMIT}`)
      .then((r) => r.json())
      .then((data: { files: string[]; total: number }) => {
        setProcessFiles((prev) => {
          const existing = prev[process];
          if (existing && offset > 0) {
            return { ...prev, [process]: { files: [...existing.files, ...data.files], total: data.total } };
          }
          return { ...prev, [process]: data };
        });
        setLoadingProcess(null);
      })
      .catch(() => setLoadingProcess(null));
  }, []);

  const toggleProcess = useCallback((process: string) => {
    setExpandedProcess((prev) => {
      const next = prev === process ? null : process;
      if (next && !processFiles[process]) {
        fetchProcessFiles(process, 0);
      }
      return next;
    });
  }, [processFiles, fetchProcessFiles]);

  const toggleTag = useCallback((tag: string) => {
    if (expandedTag === tag) {
      setExpandedTag(null);
      setTagFiles({ files: [], total: 0 });
      return;
    }
    setExpandedTag(tag);
    fetch(`/api/metadata/files-by-tag?field=tags&value=${encodeURIComponent(tag)}&offset=0&limit=${SIDEBAR_FILE_LIMIT}`)
      .then((r) => r.json())
      .then((data: { files: string[]; total: number }) => setTagFiles(data))
      .catch(() => setTagFiles({ files: [], total: 0 }));
  }, [expandedTag]);

  const loadMoreTagFiles = useCallback(() => {
    if (!expandedTag) return;
    const nextOffset = tagFiles.files.length;
    fetch(`/api/metadata/files-by-tag?field=tags&value=${encodeURIComponent(expandedTag)}&offset=${nextOffset}&limit=${SIDEBAR_FILE_LIMIT}`)
      .then((r) => r.json())
      .then((data: { files: string[]; total: number }) => {
        setTagFiles((prev) => ({ files: [...prev.files, ...data.files], total: data.total }));
      })
      .catch(() => {});
  }, [expandedTag, tagFiles]);

  if (loading) return <div className="p-3 text-sm text-muted-foreground">태그 로딩 중...</div>;
  if (!templates) return <div className="p-3 text-sm text-muted-foreground">태그 데이터 없음</div>;

  const domains = Object.keys(templates.domain_processes).sort();

  return (
    <div className="flex-1 overflow-auto text-sm">
      {/* Domain → Process → Files tree */}
      <div className="px-3 pt-3 pb-1">
        <span className="text-xs font-semibold text-muted-foreground uppercase">Domain / Process</span>
      </div>
      {domains.length === 0 && <div className="px-3 text-xs text-muted-foreground">없음</div>}
      {domains.map((d) => {
        const processes = templates.domain_processes[d] || [];
        const isExpanded = expandedDomain === d;

        return (
          <div key={d}>
            <button
              onClick={() => toggleDomain(d)}
              className="flex items-center gap-1.5 px-3 py-1 w-full hover:bg-muted/50 text-left"
            >
              {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              <span className="text-xs font-medium">{d}</span>
              <span className="text-[10px] text-muted-foreground ml-auto">{processes.length}</span>
            </button>

            {isExpanded && (
              <div className="pl-4">
                {processes.length === 0 && (
                  <div className="px-3 py-1 text-[11px] text-muted-foreground">프로세스 없음</div>
                )}
                {processes.map((p) => {
                  const isProcExpanded = expandedProcess === p;
                  const pData = processFiles[p];
                  const isLoading = loadingProcess === p;

                  return (
                    <div key={p}>
                      <button
                        onClick={() => toggleProcess(p)}
                        className="flex items-center gap-1.5 px-3 py-1 w-full hover:bg-muted/50 text-left"
                      >
                        {isProcExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                        <span className="text-xs">{p}</span>
                        {pData && <span className="text-[10px] text-muted-foreground ml-auto">{pData.total}</span>}
                      </button>

                      {isProcExpanded && (
                        <div className="pl-5">
                          {isLoading ? (
                            <div className="px-2 py-1 text-[11px] text-muted-foreground">로딩 중...</div>
                          ) : !pData || pData.files.length === 0 ? (
                            <div className="px-2 py-1 text-[11px] text-muted-foreground">문서 없음</div>
                          ) : (
                            <>
                              {pData.files.map((f) => (
                                <button key={f} onClick={() => onOpenTab(f)}
                                  className="block w-full text-left px-2 py-0.5 text-[11px] text-muted-foreground hover:text-foreground hover:bg-muted/50 truncate">
                                  {f}
                                </button>
                              ))}
                              {pData.files.length < pData.total && (
                                <button
                                  onClick={() => fetchProcessFiles(p, pData.files.length)}
                                  className="block w-full text-left px-2 py-1 text-[11px] text-primary hover:underline"
                                >
                                  더보기 ({pData.total - pData.files.length}건 남음)
                                </button>
                              )}
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}

      {/* Tags — with search + pagination */}
      <div className="px-3 pt-3 pb-1 flex items-center justify-between">
        <span className="text-xs font-semibold text-muted-foreground uppercase">Tags</span>
        {tagTotal > 0 && <span className="text-[10px] text-muted-foreground">{tagTotal}</span>}
      </div>
      <div className="px-3 pb-1">
        <input
          value={tagSearch}
          onChange={(e) => handleTagSearch(e.target.value)}
          placeholder="태그 검색..."
          className="w-full text-xs border rounded px-2 py-1 bg-background"
        />
      </div>
      {visibleTags.length === 0 && <div className="px-3 text-xs text-muted-foreground">없음</div>}
      <div className="px-3 flex flex-wrap gap-1 pb-1">
        {visibleTags.map((t) => (
          <button key={t.name} onClick={() => toggleTag(t.name)}
            className={`px-1.5 py-0.5 text-xs rounded border transition-colors ${
              expandedTag === t.name ? "bg-primary/15 border-primary/30 text-foreground" : "border-border text-muted-foreground hover:bg-muted"
            }`}>
            {t.name}
            {t.count > 0 && <span className="ml-0.5 text-[10px] opacity-60">{t.count}</span>}
          </button>
        ))}
      </div>
      {tagTotal > SIDEBAR_TAG_LIMIT && (
        <div className="px-3 pb-1 flex items-center gap-1">
          <button
            onClick={() => loadTags(tagSearch, Math.max(0, tagOffset - SIDEBAR_TAG_LIMIT))}
            disabled={tagOffset === 0}
            className="text-[10px] text-primary hover:underline disabled:opacity-30"
          >
            ◀ 이전
          </button>
          <span className="text-[10px] text-muted-foreground">
            {tagOffset + 1}-{Math.min(tagOffset + SIDEBAR_TAG_LIMIT, tagTotal)} / {tagTotal}
          </span>
          <button
            onClick={() => loadTags(tagSearch, tagOffset + SIDEBAR_TAG_LIMIT)}
            disabled={tagOffset + SIDEBAR_TAG_LIMIT >= tagTotal}
            className="text-[10px] text-primary hover:underline disabled:opacity-30"
          >
            다음 ▶
          </button>
        </div>
      )}
      {expandedTag && tagFiles.files.length > 0 && (
        <div className="px-3 pb-3">
          {tagFiles.files.map((f) => (
            <button key={f} onClick={() => onOpenTab(f)}
              className="block w-full text-left px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/50 truncate">
              {f}
            </button>
          ))}
          {tagFiles.files.length < tagFiles.total && (
            <button
              onClick={loadMoreTagFiles}
              className="block w-full text-left px-2 py-1 text-[11px] text-primary hover:underline"
            >
              더보기 ({tagFiles.total - tagFiles.files.length}건 남음)
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ── Skills Section ──────────────────────────────────────────────────

interface SkillContextMenuState {
  x: number;
  y: number;
  skill: SkillMeta;
}

function SkillContextMenu({
  state,
  onClose,
  onEdit,
  onToggle,
  onDuplicate,
  onDelete,
}: {
  state: SkillContextMenuState;
  onClose: () => void;
  onEdit: () => void;
  onToggle: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  return (
    <div
      ref={ref}
      className="fixed z-50 min-w-[160px] rounded-md border bg-popover p-1 shadow-md text-sm"
      style={{ left: state.x, top: state.y }}
    >
      <button
        onClick={() => { onEdit(); onClose(); }}
        className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 hover:bg-muted"
      >
        <Pencil className="h-3.5 w-3.5" /> 편집
      </button>
      <button
        onClick={() => { onDuplicate(); onClose(); }}
        className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 hover:bg-muted"
      >
        <Copy className="h-3.5 w-3.5" /> 복제
      </button>
      <button
        onClick={() => { onToggle(); onClose(); }}
        className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 hover:bg-muted"
      >
        {state.skill.enabled ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
        {state.skill.enabled ? "비활성화" : "활성화"}
      </button>
      <div className="my-1 border-t" />
      <button
        onClick={() => { onDelete(); onClose(); }}
        className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 hover:bg-muted text-destructive"
      >
        <Trash2 className="h-3.5 w-3.5" /> 삭제
      </button>
    </div>
  );
}

function SkillCard({
  skill,
  onClick,
  onToggle,
  onDuplicate,
  onContextMenu,
  draggable,
  onDragStart,
  onDragEnd,
}: {
  skill: SkillMeta;
  onClick: () => void;
  onToggle: () => void;
  onDuplicate: () => void;
  onContextMenu: (e: React.MouseEvent) => void;
  draggable?: boolean;
  onDragStart?: (e: React.DragEvent) => void;
  onDragEnd?: (e: React.DragEvent) => void;
}) {
  return (
    <div
      draggable={draggable}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onClick={onClick}
      onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); onContextMenu(e); }}
      className={`w-full text-left px-3 py-2 hover:bg-muted/50 group cursor-pointer ${!skill.enabled ? "opacity-40" : ""}`}
    >
      <div className="flex items-center gap-2">
        <span className="hidden group-hover:inline cursor-grab text-muted-foreground">
          <GripVertical className="h-3.5 w-3.5" />
        </span>
        <span className="group-hover:hidden text-base">{skill.icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1">
            <span className="text-xs font-medium truncate">{skill.title}</span>
            {skill.pinned && <Pin className="h-2.5 w-2.5 text-primary shrink-0" />}
            {!skill.enabled && <span className="text-[10px] text-muted-foreground">(비활성)</span>}
          </div>
          <div className="text-[11px] text-muted-foreground truncate">{skill.description}</div>
        </div>
        <div className="hidden group-hover:flex items-center gap-0.5 shrink-0">
          <span
            onClick={(e) => { e.stopPropagation(); onToggle(); }}
            className="p-0.5 rounded hover:bg-muted cursor-pointer"
            title={skill.enabled ? "비활성화" : "활성화"}
          >
            {skill.enabled ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
          </span>
          <span
            onClick={(e) => { e.stopPropagation(); onDuplicate(); }}
            className="p-0.5 rounded hover:bg-muted cursor-pointer"
            title="복제"
          >
            <Copy className="h-3 w-3" />
          </span>
        </div>
      </div>
      {skill.trigger.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-1 ml-7">
          {skill.trigger.slice(0, 3).map((t) => (
            <span key={t} className="text-[10px] bg-muted px-1.5 py-0.5 rounded">{t}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function groupByCategory(skills: SkillMeta[]): Record<string, SkillMeta[]> {
  const groups: Record<string, SkillMeta[]> = {};
  for (const s of skills) {
    const cat = s.category || "";
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(s);
  }
  // Sort within each group: pinned first, then by priority desc, then title
  for (const cat in groups) {
    groups[cat].sort((a, b) => {
      if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
      if (a.priority !== b.priority) return b.priority - a.priority;
      return a.title.localeCompare(b.title);
    });
  }
  return groups;
}

function CategoryGroup({
  category,
  skills,
  onOpenTab,
  onToggle,
  onDuplicate,
  onContextMenu,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDrop,
  isDragOver,
}: {
  category: string;
  skills: SkillMeta[];
  onOpenTab: (path: string) => void;
  onToggle: (path: string) => void;
  onDuplicate: (skill: SkillMeta) => void;
  onContextMenu: (e: React.MouseEvent, skill: SkillMeta) => void;
  onDragStart: (e: React.DragEvent, skill: SkillMeta) => void;
  onDragEnd: (e: React.DragEvent) => void;
  onDragOver: (e: React.DragEvent) => void;
  onDrop: (e: React.DragEvent, targetCategory: string) => void;
  isDragOver: boolean;
}) {
  const [expanded, setExpanded] = useState(true);
  const label = category || "미분류";

  return (
    <div
      onDragOver={onDragOver}
      onDrop={(e) => onDrop(e, category)}
      className={isDragOver ? "bg-primary/10 rounded" : ""}
    >
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-1.5 px-3 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/30"
      >
        {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        <span className="font-medium">{label}</span>
        <span className="text-[10px]">({skills.length})</span>
      </button>
      {expanded &&
        skills.map((s) => (
          <SkillCard
            key={s.path}
            skill={s}
            onClick={() => onOpenTab(s.path)}
            onToggle={() => onToggle(s.path)}
            onDuplicate={() => onDuplicate(s)}
            onContextMenu={(e) => onContextMenu(e, s)}
            draggable
            onDragStart={(e) => onDragStart(e, s)}
            onDragEnd={onDragEnd}
          />
        ))}
    </div>
  );
}

function SkillsSection({ onOpenTab }: { onOpenTab: (path: string) => void }) {
  const [skills, setSkills] = useState<SkillListResponse | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newTrigger, setNewTrigger] = useState("");
  const [newIcon, setNewIcon] = useState("⚡");
  const [newScope, setNewScope] = useState<"personal" | "shared">("personal");
  const [newCategory, setNewCategory] = useState("");
  const [newPriority, setNewPriority] = useState(5);
  const [creating, setCreating] = useState(false);
  const [showAdvancedCreate, setShowAdvancedCreate] = useState(false);
  const [skillContextMenu, setSkillContextMenu] = useState<SkillContextMenuState | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<SkillMeta | null>(null);
  const [dragSkill, setDragSkill] = useState<SkillMeta | null>(null);
  const [dragOverCategory, setDragOverCategory] = useState<string | null>(null);
  const [showSkillIntro, setShowSkillIntro] = useState(() =>
    typeof window !== "undefined" ? !localStorage.getItem("ontong:skill-intro-dismissed") : true
  );

  const refreshSkills = useCallback(() => {
    fetchSkills().then(setSkills).catch(() => setSkills(null));
  }, []);

  useEffect(() => { refreshSkills(); }, [refreshSkills]);

  const handleToggle = async (path: string) => {
    try {
      await toggleSkill(path);
      refreshSkills();
    } catch (err) {
      toast.error(`토글 실패: ${(err as Error).message}`);
    }
  };

  const handleDuplicate = async (skill: SkillMeta) => {
    try {
      const ctx = await fetchSkillContext(skill.path);
      const dup = await createSkill({
        title: `${skill.title} (사본)`,
        description: skill.description,
        trigger: skill.trigger,
        icon: skill.icon,
        scope: skill.scope,
        category: skill.category,
        priority: skill.priority,
        instructions: ctx.instructions || undefined,
        role: ctx.role || undefined,
        workflow: ctx.workflow || undefined,
        checklist: ctx.checklist || undefined,
        output_format: ctx.output_format || undefined,
        self_regulation: ctx.self_regulation || undefined,
        referenced_docs: skill.referenced_docs.length > 0 ? skill.referenced_docs : undefined,
      });
      onOpenTab(dup.path);
      refreshSkills();
    } catch (err) {
      toast.error(`복제 실패: ${(err as Error).message}`);
    }
  };

  const handleDeleteSkill = (skill: SkillMeta) => {
    setDeleteTarget(skill);
  };

  const confirmDeleteSkill = async () => {
    if (!deleteTarget) return;
    try {
      await deleteSkill(deleteTarget.path);
      refreshSkills();
      toast.success(`"${deleteTarget.title}" 삭제 완료`);
    } catch (err) {
      toast.error(`삭제 실패: ${(err as Error).message}`);
    }
    setDeleteTarget(null);
  };

  const handleSkillContextMenu = (e: React.MouseEvent, skill: SkillMeta) => {
    setSkillContextMenu({ x: e.clientX, y: e.clientY, skill });
  };

  const handleSkillDragStart = (e: React.DragEvent, skill: SkillMeta) => {
    setDragSkill(skill);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", skill.path);
  };

  const handleSkillDragEnd = () => {
    setDragSkill(null);
    setDragOverCategory(null);
  };

  const handleSkillDragOver = (e: React.DragEvent, category: string) => {
    if (!dragSkill) return;
    if (dragSkill.category === category) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDragOverCategory(category);
  };

  const handleSkillDrop = async (e: React.DragEvent, targetCategory: string) => {
    e.preventDefault();
    setDragOverCategory(null);
    if (!dragSkill || dragSkill.category === targetCategory) return;
    try {
      await moveSkill(dragSkill.path, targetCategory);
      refreshSkills();
      toast.success(`"${dragSkill.title}" → ${targetCategory || "미분류"} 이동 완료`);
    } catch (err) {
      toast.error(`이동 실패: ${(err as Error).message}`);
    }
    setDragSkill(null);
  };

  const handleCreate = async () => {
    if (!newTitle.trim()) return;
    setCreating(true);
    try {
      const triggers = newTrigger.split(",").map((s) => s.trim()).filter(Boolean);
      const skill = await createSkill({
        title: newTitle.trim(),
        description: newDesc.trim(),
        trigger: triggers,
        icon: newIcon || "⚡",
        scope: newScope,
        category: newCategory.trim(),
        priority: newPriority,
      });
      onOpenTab(skill.path);
      setShowCreate(false);
      setNewTitle(""); setNewDesc(""); setNewTrigger(""); setNewIcon("⚡");
      setNewScope("personal"); setNewCategory(""); setNewPriority(5);
      refreshSkills();
    } catch (err) {
      toast.error(`스킬 생성 실패: ${(err as Error).message}`);
    } finally {
      setCreating(false);
    }
  };

  const filterSkills = (list: SkillMeta[]) => {
    if (!searchQuery.trim()) return list;
    const q = searchQuery.toLowerCase();
    return list.filter(
      (s) =>
        s.title.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q) ||
        s.trigger.some((t) => t.toLowerCase().includes(q))
    );
  };

  const personalFiltered = filterSkills(skills?.personal ?? []);
  const systemFiltered = filterSkills(skills?.system ?? []);
  const personalGroups = groupByCategory(personalFiltered);
  const systemGroups = groupByCategory(systemFiltered);
  const sortedCatKeys = (groups: Record<string, SkillMeta[]>) =>
    Object.keys(groups).sort((a, b) => {
      if (!a) return 1;
      if (!b) return -1;
      return a.localeCompare(b);
    });

  const renderGroups = (groups: Record<string, SkillMeta[]>) => {
    const keys = sortedCatKeys(groups);
    if (keys.length === 0) return null;
    // If only one group with no category, skip the collapsible wrapper
    if (keys.length === 1 && keys[0] === "") {
      return groups[""].map((s) => (
        <SkillCard
          key={s.path}
          skill={s}
          onClick={() => onOpenTab(s.path)}
          onToggle={() => handleToggle(s.path)}
          onDuplicate={() => handleDuplicate(s)}
          onContextMenu={(e) => handleSkillContextMenu(e, s)}
          draggable
          onDragStart={(e) => handleSkillDragStart(e, s)}
          onDragEnd={handleSkillDragEnd}
        />
      ));
    }
    return keys.map((cat) => (
      <CategoryGroup
        key={cat || "__uncategorized"}
        category={cat}
        skills={groups[cat]}
        onOpenTab={onOpenTab}
        onToggle={handleToggle}
        onDuplicate={handleDuplicate}
        onContextMenu={handleSkillContextMenu}
        onDragStart={handleSkillDragStart}
        onDragEnd={handleSkillDragEnd}
        onDragOver={(e) => handleSkillDragOver(e, cat)}
        onDrop={handleSkillDrop}
        isDragOver={dragOverCategory === cat}
      />
    ));
  };

  return (
    <div className="flex-1 overflow-auto text-sm">
      {/* Search */}
      <div className="px-3 pt-2 pb-1">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="스킬 검색..."
            className="w-full text-xs pl-7 pr-2 py-1 rounded border bg-background"
          />
        </div>
      </div>

      {/* Intro banner — dismissible, shown once */}
      {showSkillIntro && (
        <div className="mx-3 mt-2 p-2.5 rounded-lg bg-primary/5 border border-primary/20 text-xs space-y-1">
          <div className="flex items-center justify-between">
            <span className="font-semibold flex items-center gap-1">
              <Zap className="h-3 w-3 text-primary" />
              스킬이란?
            </span>
            <button onClick={() => {
              setShowSkillIntro(false);
              localStorage.setItem("ontong:skill-intro-dismissed", "1");
            }} className="text-muted-foreground hover:text-foreground">
              <X className="h-3 w-3" />
            </button>
          </div>
          <p className="text-muted-foreground leading-relaxed">
            스킬은 AI 코파일럿의 <strong className="text-foreground">응답 방식을 커스터마이징</strong>하는 템플릿입니다.
            역할, 참조 문서, 출력 형식 등을 미리 정의해 두면, 질문할 때 자동으로 적용됩니다.
          </p>
        </div>
      )}

      {/* Personal skills */}
      <div className="px-3 pt-2 pb-1 flex items-center justify-between">
        <span className="text-xs font-semibold text-muted-foreground uppercase">내 스킬</span>
        <button onClick={() => setShowCreate((v) => !v)}
          className="p-0.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground" title="새 스킬">
          {showCreate ? <X className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
        </button>
      </div>

      {/* Create form (inline) */}
      {showCreate && (
        <div className="px-3 pb-2 space-y-1.5 border-b mb-1">
          <input value={newTitle} onChange={(e) => setNewTitle(e.target.value)}
            placeholder="스킬 이름" className="w-full text-xs px-2 py-1 rounded border bg-background" />
          <input value={newDesc} onChange={(e) => setNewDesc(e.target.value)}
            placeholder="한 줄 설명" className="w-full text-xs px-2 py-1 rounded border bg-background" />
          <input value={newTrigger} onChange={(e) => setNewTrigger(e.target.value)}
            placeholder="트리거 키워드 (쉼표 구분)" className="w-full text-xs px-2 py-1 rounded border bg-background" />
          <div className="flex items-center gap-2">
            <input value={newIcon} onChange={(e) => setNewIcon(e.target.value)}
              placeholder="아이콘" className="w-12 text-xs px-2 py-1 rounded border bg-background text-center" />
            <select value={newScope} onChange={(e) => setNewScope(e.target.value as "personal" | "shared")}
              className="flex-1 text-xs px-2 py-1 rounded border bg-background">
              <option value="personal">개인</option>
              <option value="shared">공용</option>
            </select>
          </div>
          <div className="flex items-center gap-2">
            <input
              value={newCategory}
              onChange={(e) => setNewCategory(e.target.value)}
              placeholder="카테고리 (예: HR)"
              list="skill-categories"
              className="flex-1 text-xs px-2 py-1 rounded border bg-background"
            />
            <datalist id="skill-categories">
              {(skills?.categories ?? []).map((c) => <option key={c} value={c} />)}
            </datalist>
            <label className="flex items-center gap-1 text-xs text-muted-foreground">
              우선순위
              <input
                type="number"
                min={1}
                max={10}
                value={newPriority}
                onChange={(e) => setNewPriority(Math.max(1, Math.min(10, Number(e.target.value) || 5)))}
                className="w-12 text-xs px-1 py-1 rounded border bg-background text-center"
              />
            </label>
          </div>
          <div className="flex gap-2">
            <button onClick={handleCreate} disabled={creating || !newTitle.trim()}
              className="flex-1 text-xs px-3 py-1 rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
              {creating ? "생성 중..." : "생성"}
            </button>
            <button
              onClick={() => { setShowCreate(false); setShowAdvancedCreate(true); }}
              className="text-xs px-2 py-1 rounded border hover:bg-muted text-muted-foreground hover:text-foreground"
              title="고급 설정으로 생성"
            >
              <Settings className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      <SkillCreateDialog
        open={showAdvancedCreate}
        onOpenChange={setShowAdvancedCreate}
        onCreated={(path) => { onOpenTab(path); refreshSkills(); }}
        categories={skills?.categories ?? []}
      />

      {personalFiltered.length > 0 ? (
        renderGroups(personalGroups)
      ) : (
        !showCreate && (searchQuery ? (
          <div className="px-3 py-2 text-xs text-muted-foreground">검색 결과 없음</div>
        ) : (
          <div className="px-3 py-4 text-center space-y-2">
            <Zap className="h-6 w-6 mx-auto text-muted-foreground/50" />
            <p className="text-xs text-muted-foreground">아직 만든 스킬이 없습니다</p>
            <p className="text-[11px] text-muted-foreground/70">
              자주 쓰는 질문 패턴이 있다면,<br />스킬로 만들어 AI 응답을 맞춤 설정하세요.
            </p>
            <button
              onClick={() => setShowCreate(true)}
              className="text-xs text-primary hover:underline font-medium"
            >
              + 첫 번째 스킬 만들기
            </button>
          </div>
        ))
      )}

      {/* Shared skills */}
      <div className="px-3 pt-3 pb-1">
        <span className="text-xs font-semibold text-muted-foreground uppercase">공용 스킬</span>
      </div>
      {systemFiltered.length > 0 ? (
        renderGroups(systemGroups)
      ) : (
        searchQuery ? (
          <div className="px-3 py-2 text-xs text-muted-foreground">검색 결과 없음</div>
        ) : (
          <div className="px-3 py-3 text-center space-y-1">
            <p className="text-xs text-muted-foreground">공용 스킬이 없습니다</p>
            <p className="text-[11px] text-muted-foreground/70">
              스킬 생성 시 &apos;범위&apos;를 &apos;공용&apos;으로 선택하면<br />여기에 표시됩니다.
            </p>
          </div>
        )
      )}

      {/* Skill context menu */}
      {skillContextMenu && (
        <SkillContextMenu
          state={skillContextMenu}
          onClose={() => setSkillContextMenu(null)}
          onEdit={() => onOpenTab(skillContextMenu.skill.path)}
          onToggle={() => handleToggle(skillContextMenu.skill.path)}
          onDuplicate={() => handleDuplicate(skillContextMenu.skill)}
          onDelete={() => handleDeleteSkill(skillContextMenu.skill)}
        />
      )}

      {/* Skill delete confirmation dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}>
        <DialogContent className="sm:max-w-sm" onKeyDown={(e) => { if (e.key === "Enter") confirmDeleteSkill(); }}>
          <DialogHeader>
            <DialogTitle>스킬 삭제</DialogTitle>
            <DialogDescription>
              <span className="font-semibold text-foreground">{deleteTarget?.title}</span> 스킬을 삭제하시겠습니까?
              <br />이 작업은 되돌릴 수 없습니다.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>취소</Button>
            <Button variant="destructive" onClick={confirmDeleteSkill} autoFocus>삭제</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ── Settings Section ─────────────────────────────────────────────────

function SettingsSection({ onOpenVirtualTab }: { onOpenVirtualTab: (tabType: import("@/types").VirtualTabType) => void }) {
  const itemClass = "flex items-center gap-2.5 mx-2 px-2 py-2 rounded-md hover:bg-muted/60 text-left transition-colors";
  return (
    <div className="flex-1 overflow-auto text-sm">
      <div className="px-3 pt-3 pb-2">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">관리</span>
      </div>
      <div className="space-y-0.5">
        <button onClick={() => onOpenVirtualTab("metadata-templates")} className={itemClass}>
          <Tags className="h-4 w-4 text-muted-foreground shrink-0" />
          <div className="min-w-0">
            <div className="text-xs font-medium truncate">메타데이터 템플릿</div>
            <div className="text-[11px] text-muted-foreground truncate">Domain, Process, Tags 관리</div>
          </div>
        </button>
        <button onClick={() => onOpenVirtualTab("untagged-dashboard")} className={itemClass}>
          <File className="h-4 w-4 text-muted-foreground shrink-0" />
          <div className="min-w-0">
            <div className="text-xs font-medium truncate">미태깅 문서</div>
            <div className="text-[11px] text-muted-foreground truncate">태그 없는 문서 목록 + 일괄 태깅</div>
          </div>
        </button>
        <button onClick={() => onOpenVirtualTab("conflict-dashboard")} className={itemClass}>
          <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0" />
          <div className="min-w-0">
            <div className="text-xs font-medium truncate">관련 문서 관리</div>
            <div className="text-[11px] text-muted-foreground truncate">유사 문서 분류 + AI 분석 + 해결</div>
          </div>
        </button>
        <button onClick={() => onOpenVirtualTab("maintenance-digest")} className={itemClass}>
          <ClipboardList className="h-4 w-4 text-orange-500 shrink-0" />
          <div className="min-w-0">
            <div className="text-xs font-medium truncate">관리가 필요한 문서</div>
            <div className="text-[11px] text-muted-foreground truncate">오래됨 / 신뢰도 낮음 / 미해결 관련</div>
          </div>
        </button>
        <button onClick={() => onOpenVirtualTab("document-graph")} className={itemClass}>
          <Network className="h-4 w-4 text-indigo-500 shrink-0" />
          <div className="min-w-0">
            <div className="text-xs font-medium truncate">문서 관계 그래프</div>
            <div className="text-[11px] text-muted-foreground truncate">문서 간 연결 관계 시각화</div>
          </div>
        </button>
        <button onClick={() => onOpenVirtualTab("permission-editor")} className={itemClass}>
          <Shield className="h-4 w-4 text-rose-500 shrink-0" />
          <div className="min-w-0">
            <div className="text-xs font-medium truncate">접근 권한 관리</div>
            <div className="text-[11px] text-muted-foreground truncate">폴더/문서별 읽기·쓰기 제어</div>
          </div>
        </button>
        <button onClick={() => onOpenVirtualTab("scoring-dashboard")} className={itemClass}>
          <Gauge className="h-4 w-4 text-emerald-500 shrink-0" />
          <div className="min-w-0">
            <div className="text-xs font-medium truncate">신뢰도 설정</div>
            <div className="text-[11px] text-muted-foreground truncate">점수 가중치, 임계값, 공식 확인</div>
          </div>
        </button>
      </div>
    </div>
  );
}

// ── Unused Images Panel ──────────────────────────────────────────────

function UnusedImagesPanel() {
  const [unused, setUnused] = useState<UnusedImage[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const scan = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/files/assets/unused");
      if (!res.ok) throw new Error();
      const data = await res.json();
      setUnused(data.unused);
      setOpen(true);
    } catch {
      toast.error("이미지 스캔 실패");
    } finally {
      setLoading(false);
    }
  }, []);

  const deleteAll = useCallback(async () => {
    setDeleting(true);
    try {
      const res = await fetch("/api/files/assets/unused", { method: "DELETE" });
      if (!res.ok) throw new Error();
      const data = await res.json();
      toast.success(`미사용 이미지 ${data.count}개 삭제 완료`);
      setUnused([]);
      setOpen(false);
    } catch {
      toast.error("삭제 실패");
    } finally {
      setDeleting(false);
    }
  }, []);

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes}B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  };

  const totalSize = unused.reduce((s, i) => s + i.size, 0);

  return (
    <div className="shrink-0 border-t">
      <button
        onClick={scan}
        disabled={loading}
        className="flex items-center gap-2 w-full px-3 py-2 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
      >
        {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ImageOff className="h-3.5 w-3.5" />}
        미사용 이미지 정리
      </button>

      {open && (
        <div className="px-3 pb-2 space-y-2">
          {unused.length === 0 ? (
            <p className="text-xs text-muted-foreground">미사용 이미지가 없습니다.</p>
          ) : (
            <>
              <div className="max-h-32 overflow-auto space-y-1">
                {unused.map((img) => (
                  <div key={img.filename} className="flex items-center gap-2 text-xs">
                    <span className="truncate flex-1 text-muted-foreground" title={img.filename}>
                      {img.filename}
                    </span>
                    <span className="shrink-0 text-muted-foreground/60">
                      {formatSize(img.size)}
                    </span>
                  </div>
                ))}
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">
                  {unused.length}개 · {formatSize(totalSize)}
                </span>
                <button
                  onClick={deleteAll}
                  disabled={deleting}
                  className="flex items-center gap-1 px-2 py-1 text-xs rounded-md bg-destructive text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50 transition-colors"
                >
                  {deleting ? <Loader2 className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
                  전체 삭제
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ── Tree helpers ────────────────────────────────────────────────────

/** Recursively update children of a node at the given path */
function updateNodeChildren(
  nodes: WikiTreeNode[],
  targetPath: string,
  children: WikiTreeNode[],
): WikiTreeNode[] {
  return nodes.map((node) => {
    if (node.path === targetPath) {
      return { ...node, children, has_children: children.length > 0 };
    }
    if (node.is_dir && node.children.length > 0 && targetPath.startsWith(node.path + "/")) {
      return { ...node, children: updateNodeChildren(node.children, targetPath, children) };
    }
    return node;
  });
}

/** Remove a node from the tree by path */
function removeTreeNode(nodes: WikiTreeNode[], path: string): WikiTreeNode[] {
  return nodes
    .filter((n) => n.path !== path)
    .map((n) =>
      n.is_dir && n.children.length > 0
        ? { ...n, children: removeTreeNode(n.children, path) }
        : n
    );
}

/** Add a node to a parent in the tree (sorted by name, dirs first) */
function addTreeNode(nodes: WikiTreeNode[], parentPath: string, newNode: WikiTreeNode): WikiTreeNode[] {
  if (parentPath === "") {
    // Add to root
    const result = [...nodes, newNode];
    return sortNodes(result);
  }
  return nodes.map((n) => {
    if (n.path === parentPath && n.is_dir) {
      return { ...n, children: sortNodes([...n.children, newNode]), has_children: true };
    }
    if (n.is_dir && n.children.length > 0 && parentPath.startsWith(n.path + "/")) {
      return { ...n, children: addTreeNode(n.children, parentPath, newNode) };
    }
    return n;
  });
}

/** Update paths recursively when a node is renamed/moved */
function updateNodePath(node: WikiTreeNode, oldPrefix: string, newPrefix: string): WikiTreeNode {
  const newPath = node.path.replace(oldPrefix, newPrefix);
  return {
    ...node,
    path: newPath,
    children: node.children.map((c) => updateNodePath(c, oldPrefix, newPrefix)),
  };
}

/** Sort nodes: directories first, then alphabetical */
function sortNodes(nodes: WikiTreeNode[]): WikiTreeNode[] {
  return [...nodes].sort((a, b) => {
    if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
}

// ── Main TreeNav ────────────────────────────────────────────────────

type SidebarSection = "files" | "tags" | "skills" | "settings";

export function TreeNav() {
  const [section, setSection] = useState<SidebarSection>("files");
  const [tree, setTree] = useState<WikiTreeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const [creatingIn, setCreatingIn] = useState<string | null>(null);
  const [creatingType, setCreatingType] = useState<"file" | "folder" | null>(null);
  const [renamingNode, setRenamingNode] = useState<WikiTreeNode | null>(null);
  const [dragOverlay, setDragOverlay] = useState<WikiTreeNode | null>(null);
  const [deprecatedMap, setDeprecatedMap] = useState<Record<string, string>>({});
  const [newVersionTarget, setNewVersionTarget] = useState<string | null>(null);
  const [newVersionName, setNewVersionName] = useState("");
  const [newVersionCreating, setNewVersionCreating] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<{ path: string; type: "file" | "folder" } | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // Share dialog / properties panel
  const [shareDialogPath, setShareDialogPath] = useState<string | null>(null);
  const [propertiesPath, setPropertiesPath] = useState<string | null>(null);

  // Collapsible section headers — persisted to localStorage
  const [sectionMyDocs, setSectionMyDocs] = useState<boolean>(() => {
    if (typeof window === "undefined") return true;
    return localStorage.getItem("ontong:tree-section-mydocs") !== "false";
  });
  const [sectionWiki, setSectionWiki] = useState<boolean>(() => {
    if (typeof window === "undefined") return true;
    return localStorage.getItem("ontong:tree-section-wiki") !== "false";
  });

  const { user } = useAuth();

  const toggleSectionMyDocs = useCallback(() => {
    setSectionMyDocs((v) => {
      const next = !v;
      localStorage.setItem("ontong:tree-section-mydocs", String(next));
      return next;
    });
  }, []);
  const toggleSectionWiki = useCallback(() => {
    setSectionWiki((v) => {
      const next = !v;
      localStorage.setItem("ontong:tree-section-wiki", String(next));
      return next;
    });
  }, []);

  const openTab = useWorkspaceStore((s) => s.openTab);
  const openVirtualTab = useWorkspaceStore((s) => s.openVirtualTab);
  const closeTabById = useWorkspaceStore((s) => s.closeTab);
  const updateTabPath = useWorkspaceStore((s) => s.updateTabPath);
  const tabs = useWorkspaceStore((s) => s.tabs);
  const activeTabId = useWorkspaceStore((s) => s.activeTabId);
  const treeVersion = useWorkspaceStore((s) => s.treeVersion);
  const activeFilePath = tabs.find((t) => t.id === activeTabId)?.filePath ?? null;
  const openSearch = useSearchStore((s) => s.setOpen);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  );

  const fetchTreeData = useCallback(() => {
    setLoading(true);
    setError(null);
    fetch("/api/wiki/tree?depth=1")
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(setTree)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  // Load children for a folder (lazy loading)
  const loadChildren = useCallback(async (folderPath: string) => {
    const children = await fetchSubtree(folderPath);
    setTree((prev) => updateNodeChildren(prev, folderPath, children));
  }, []);

  useEffect(() => { fetchTreeData(); }, [fetchTreeData]);
  useEffect(() => { if (treeVersion > 0) fetchTreeData(); }, [treeVersion, fetchTreeData]);

  // Fetch document statuses for deprecated styling
  useEffect(() => {
    fetch("/api/metadata/statuses")
      .then((r) => (r.ok ? r.json() : {}))
      .then(setDeprecatedMap)
      .catch(() => {});
  }, [treeVersion]);

  // ── SSE real-time tree updates ─────────────────────────────────
  useEffect(() => {
    const es = new EventSource("/api/events");
    es.addEventListener("tree_change", (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.action === "update" || data.action === "add") {
          // Reload the parent folder subtree
          const parent = data.path.includes("/")
            ? data.path.split("/").slice(0, -1).join("/")
            : "";
          if (parent) {
            fetchSubtree(parent).then((children) =>
              setTree((prev) => updateNodeChildren(prev, parent, children))
            ).catch(() => {});
          } else {
            fetchTreeData();
          }
        } else if (data.action === "remove") {
          setTree((prev) => removeTreeNode(prev, data.path));
        } else if (data.action === "move") {
          fetchTreeData();
        }
      } catch {}
    });
    es.onerror = () => {
      // Auto-reconnect is built into EventSource
    };
    return () => es.close();
  }, [fetchTreeData]);

  // ── Drag & Drop ─────────────────────────────────────────────────

  const handleDragEnd = useCallback(async (event: DragEndEvent) => {
    setDragOverlay(null);
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const draggedNode = (active.data.current as { node: WikiTreeNode }).node;
    const targetFolderPath = (over.data.current as { folderPath: string }).folderPath;

    // Compute new path
    const name = draggedNode.path.split("/").pop()!;
    const newPath = targetFolderPath ? `${targetFolderPath}/${name}` : name;

    if (newPath === draggedNode.path) return;

    try {
      await apiMove(draggedNode.path, newPath, draggedNode.is_dir);

      // Update open tabs if file was moved
      if (!draggedNode.is_dir) {
        const tab = tabs.find((t) => t.filePath === draggedNode.path);
        if (tab) updateTabPath(tab.id, newPath);
      }

      toast.success(`"${name}" 이동됨`);
      // Optimistic update: remove from old location, add to new
      const movedNode = updateNodePath(draggedNode, draggedNode.path, newPath);
      movedNode.name = name;
      setTree((prev) => addTreeNode(removeTreeNode(prev, draggedNode.path), targetFolderPath, movedNode));
    } catch (err) {
      toast.error(`이동 실패: ${(err as Error).message}`);
    }
  }, [tabs, updateTabPath]);

  // ── Context Menu ────────────────────────────────────────────────

  const handleContextMenu = useCallback((e: React.MouseEvent, node: WikiTreeNode) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({ x: e.clientX, y: e.clientY, node });
  }, []);

  const handleRootContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setContextMenu({ x: e.clientX, y: e.clientY, node: null });
  }, []);

  // ── Rename ──────────────────────────────────────────────────────

  const handleRenameSubmit = useCallback(async (node: WikiTreeNode, newName: string) => {
    setRenamingNode(null);
    if (newName === node.name) return;

    const parent = node.path.includes("/")
      ? node.path.substring(0, node.path.lastIndexOf("/"))
      : "";
    const finalName = (!node.is_dir && !newName.includes(".")) ? `${newName}.md` : newName;
    const newPath = parent ? `${parent}/${finalName}` : finalName;

    try {
      await apiMove(node.path, newPath, node.is_dir);

      if (!node.is_dir) {
        const tab = tabs.find((t) => t.filePath === node.path);
        if (tab) updateTabPath(tab.id, newPath);
      }

      toast.success(`"${node.name}" → "${finalName}"`);
      // Optimistic update: rename node in tree
      setTree((prev) => {
        const updated = updateNodePath(node, node.path, newPath);
        updated.name = finalName;
        const parentPath = node.path.includes("/") ? node.path.substring(0, node.path.lastIndexOf("/")) : "";
        return addTreeNode(removeTreeNode(prev, node.path), parentPath, updated);
      });
    } catch (err) {
      toast.error(`이름 변경 실패: ${(err as Error).message}`);
    }
  }, [tabs, updateTabPath]);

  // ── Delete ──────────────────────────────────────────────────────

  const handleDeleteFile = useCallback((path: string) => {
    setDeleteConfirm({ path, type: "file" });
  }, []);

  const handleDeleteFolder = useCallback((path: string) => {
    setDeleteConfirm({ path, type: "folder" });
  }, []);

  const confirmDelete = useCallback(async () => {
    if (!deleteConfirm) return;
    const { path, type } = deleteConfirm;
    const name = path.split("/").pop() ?? path;
    setDeleteLoading(true);
    try {
      const endpoint = type === "file"
        ? `/api/wiki/file/${encodeURIComponent(path)}`
        : `/api/wiki/folder/${encodeURIComponent(path)}`;
      const res = await fetch(endpoint, { method: "DELETE" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const detail = body.detail;
        if (res.status === 409 && detail?.referenced_by) {
          const allRefs = detail.referenced_by as string[];
          const names = allRefs.map((p: string) => p.split("/").pop());
          const desc = names.length <= 3
            ? `참조 문서: ${names.join(", ")}`
            : `참조 문서: ${names.slice(0, 2).join(", ")} 외 ${names.length - 2}건`;
          toast.error("삭제할 수 없습니다", {
            description: `${desc}\n참조를 먼저 제거해주세요.`,
            duration: 6000,
          });
          return;
        }
        const msg = typeof detail === "string" ? detail
          : typeof detail?.message === "string" ? detail.message
          : `서버 오류 (${res.status})`;
        throw new Error(msg);
      }
      if (type === "file") {
        const tab = tabs.find((t) => t.filePath === path);
        if (tab) closeTabById(tab.id);
      }
      toast.success(`"${name}" 삭제됨`);
      setTree((prev) => removeTreeNode(prev, path));
    } catch (err) {
      toast.error("삭제 실패", {
        description: (err as Error).message,
        duration: 5000,
      });
    } finally {
      setDeleteLoading(false);
      setDeleteConfirm(null);
    }
  }, [deleteConfirm, tabs, closeTabById]);

  // ── Create ──────────────────────────────────────────────────────

  const handleCreateSubmit = useCallback(async (name: string) => {
    const parentPath = creatingIn === "__root__" ? "" : creatingIn ?? "";
    const type = creatingType;
    setCreatingIn(null);
    setCreatingType(null);

    if (type === "file") {
      const fileName = name.endsWith(".md") ? name : `${name}.md`;
      const fullPath = parentPath ? `${parentPath}/${fileName}` : fileName;
      try {
        const res = await fetch(`/api/wiki/file/${encodeURIComponent(fullPath)}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: `# ${name.replace(/\.md$/, "")}\n\n` }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        toast.success(`"${fileName}" 생성됨`);
        const newNode: WikiTreeNode = { name: fileName, path: fullPath, is_dir: false, children: [] };
        setTree((prev) => addTreeNode(prev, parentPath, newNode));
        openTab(fullPath);
      } catch (err) {
        toast.error(`생성 실패: ${(err as Error).message}`);
      }
    } else if (type === "folder") {
      const fullPath = parentPath ? `${parentPath}/${name}` : name;
      try {
        const res = await fetch(`/api/wiki/folder/${encodeURIComponent(fullPath)}`, { method: "POST" });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || `HTTP ${res.status}`);
        }
        toast.success(`"${name}" 폴더 생성됨`);
        const newNode: WikiTreeNode = { name, path: fullPath, is_dir: true, children: [], has_children: false };
        setTree((prev) => addTreeNode(prev, parentPath, newNode));
      } catch (err) {
        toast.error(`폴더 생성 실패: ${(err as Error).message}`);
      }
    }
  }, [creatingIn, creatingType, openTab]);

  // ── New Version ─────────────────────────────────────────────────

  const handleNewVersionOpen = useCallback((path: string) => {
    const name = path.split("/").pop()?.replace(".md", "") ?? "";
    const vMatch = name.match(/^(.*?)[-_]?v(\d+)$/i);
    const suggested = vMatch ? `${vMatch[1]}-v${parseInt(vMatch[2]) + 1}.md` : `${name}-v2.md`;
    setNewVersionTarget(path);
    setNewVersionName(suggested);
  }, []);

  const handleNewVersionSubmit = useCallback(async () => {
    if (!newVersionTarget || !newVersionName.trim()) return;
    setNewVersionCreating(true);
    const folder = newVersionTarget.includes("/") ? newVersionTarget.substring(0, newVersionTarget.lastIndexOf("/")) : "";
    const fileName = newVersionName.endsWith(".md") ? newVersionName : `${newVersionName}.md`;
    const newPath = folder ? `${folder}/${fileName}` : fileName;

    try {
      const res = await fetch("/api/wiki/create-new-version", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ old_path: newVersionTarget, new_path: newPath }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const detail = typeof data.detail === "string" ? data.detail : `서버 오류 (${res.status})`;
        throw new Error(detail);
      }
      const result = await res.json().catch(() => ({}));
      toast.success(`새 버전 "${fileName}" 생성됨`, {
        description: result.old_status === "deprecated" ? "이전 버전이 자동으로 폐기 처리되었습니다." : undefined,
      });
      // Update deprecated map for old doc
      if (result.old_status === "deprecated" && newVersionTarget) {
        setDeprecatedMap((prev) => ({ ...prev, [newVersionTarget]: "deprecated" }));
      }
      // Add to tree
      const parentPath = folder;
      const newNode: WikiTreeNode = { name: fileName, path: newPath, is_dir: false, children: [] };
      setTree((prev) => addTreeNode(prev, parentPath, newNode));
      openTab(newPath);
      setNewVersionTarget(null);
    } catch (err) {
      toast.error("새 버전 생성 실패", { description: (err as Error).message, duration: 5000 });
    } finally {
      setNewVersionCreating(false);
    }
  }, [newVersionTarget, newVersionName, openTab]);

  // ── Render ──────────────────────────────────────────────────────

  if (loading) return (
    <div className="p-3 space-y-2 animate-pulse">
      {[1, 0.7, 0.85, 0.6, 0.75, 0.5].map((w, i) => (
        <div key={i} className="flex items-center gap-2" style={{ paddingLeft: i > 2 ? 16 : 0 }}>
          <div className="h-3.5 w-3.5 rounded bg-muted shrink-0" />
          <div className="h-3 rounded bg-muted" style={{ width: `${w * 100}%` }} />
        </div>
      ))}
    </div>
  );
  if (error) return <div className="p-3 text-sm text-destructive">트리 로드 실패: {error}</div>;

  const sectionBtnClass = (s: SidebarSection) =>
    `flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-md text-xs font-medium transition-colors whitespace-nowrap ${section === s ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`;

  return (
    <DndContext
      sensors={sensors}
      onDragStart={(e) => setDragOverlay((e.active.data.current as { node: WikiTreeNode }).node)}
      onDragEnd={handleDragEnd}
      onDragCancel={() => setDragOverlay(null)}
    >
      <div className="flex flex-col h-full">
        {/* Header with section tabs */}
        <div className="@container flex items-center px-2 py-2 border-b shrink-0 min-w-0">
          <div className="flex items-center gap-0.5 flex-1 min-w-0">
            <button onClick={() => setSection("files")} className={sectionBtnClass("files")} title="파일 트리">
              <FolderTree className="h-3.5 w-3.5 shrink-0" />
              <span className="hidden @min-[180px]:inline truncate">파일</span>
            </button>
            <button onClick={() => setSection("tags")} className={sectionBtnClass("tags")} title="태그 브라우저">
              <Tags className="h-3.5 w-3.5 shrink-0" />
              <span className="hidden @min-[180px]:inline truncate">태그</span>
            </button>
            <button onClick={() => setSection("skills")} className={sectionBtnClass("skills")} title="스킬">
              <Zap className="h-3.5 w-3.5 shrink-0" />
              <span className="hidden @min-[180px]:inline truncate">스킬</span>
            </button>
            <button onClick={() => setSection("settings")} className={sectionBtnClass("settings")} title="관리">
              <Settings className="h-3.5 w-3.5 shrink-0" />
              <span className="hidden @min-[180px]:inline truncate">관리</span>
            </button>
          </div>
          <button onClick={() => openSearch(true)}
            className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground mr-1" title="문서 검색 (Ctrl+K)">
            <Search className="h-3.5 w-3.5" />
          </button>
          {section === "files" && (
            <div className="flex items-center gap-0.5">
              <button onClick={() => { setCreatingIn("__root__"); setCreatingType("file"); }}
                className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground" title="새 문서">
                <FilePlus className="h-4 w-4" />
              </button>
              <button onClick={() => { setCreatingIn("__root__"); setCreatingType("folder"); }}
                className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground" title="새 폴더">
                <FolderPlus className="h-4 w-4" />
              </button>
              <button onClick={fetchTreeData}
                className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground" title="새로고침">
                <RefreshCw className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>

        {/* Section content */}
        {section === "files" && (() => {
          const userId = user?.id ?? "";
          const myDocNodes = userId
            ? tree.filter((n) => n.path === `@${userId}` || n.path.startsWith(`@${userId}/`))
            : [];
          const wikiNodes = tree.filter(
            (n) =>
              !myDocNodes.includes(n) &&
              n.path !== "_skills" && !n.path.startsWith("_skills/") &&
              !(userId && (n.path === `@${userId}` || n.path.startsWith(`@${userId}/`)))
          );

          const renderSection = (
            label: string,
            nodes: WikiTreeNode[],
            expanded: boolean,
            onToggle: () => void,
          ) => (
            <>
              <button
                onClick={onToggle}
                className="flex items-center gap-1 w-full px-3 py-1 text-[11px] font-semibold text-muted-foreground uppercase hover:text-foreground select-none"
              >
                {expanded
                  ? <ChevronDown className="h-3 w-3 shrink-0" />
                  : <ChevronRight className="h-3 w-3 shrink-0" />
                }
                {label}
              </button>
              {expanded && nodes.map((node) => (
                <DraggableTreeItem key={node.path} node={node} depth={0}
                  renamingPath={renamingNode?.path ?? null}
                  activeFilePath={activeFilePath}
                  onRenameSubmit={handleRenameSubmit} onRenameCancel={() => setRenamingNode(null)}
                  onContextMenu={handleContextMenu} onOpenTab={openTab}
                  creatingIn={creatingIn} creatingType={creatingType}
                  onCreateSubmit={handleCreateSubmit}
                  onCreateCancel={() => { setCreatingIn(null); setCreatingType(null); }}
                  onLoadChildren={loadChildren} statusMap={deprecatedMap} />
              ))}
            </>
          );

          const useSections = userId && myDocNodes.length > 0;

          return (
            <>
              <RootDropZone onContextMenu={handleRootContextMenu}>
                {creatingIn === "__root__" && creatingType === "file" && (
                  <InlineInput icon={File} placeholder="파일명.md" indent={8}
                    onSubmit={handleCreateSubmit} onCancel={() => { setCreatingIn(null); setCreatingType(null); }} />
                )}
                {creatingIn === "__root__" && creatingType === "folder" && (
                  <InlineInput icon={Folder} placeholder="폴더명" indent={8}
                    onSubmit={handleCreateSubmit} onCancel={() => { setCreatingIn(null); setCreatingType(null); }} />
                )}
                {tree.length === 0 && !creatingIn ? (
                  <div className="p-3 text-sm text-muted-foreground">파일이 없습니다</div>
                ) : useSections ? (
                  <>
                    {myDocNodes.length > 0 && renderSection("내 문서", myDocNodes, sectionMyDocs, toggleSectionMyDocs)}
                    {wikiNodes.length > 0 && renderSection("위키", wikiNodes, sectionWiki, toggleSectionWiki)}
                  </>
                ) : (
                  tree.map((node) => (
                    <DraggableTreeItem key={node.path} node={node} depth={0}
                      renamingPath={renamingNode?.path ?? null}
                      activeFilePath={activeFilePath}
                      onRenameSubmit={handleRenameSubmit} onRenameCancel={() => setRenamingNode(null)}
                      onContextMenu={handleContextMenu} onOpenTab={openTab}
                      creatingIn={creatingIn} creatingType={creatingType}
                      onCreateSubmit={handleCreateSubmit}
                      onCreateCancel={() => { setCreatingIn(null); setCreatingType(null); }}
                      onLoadChildren={loadChildren} statusMap={deprecatedMap} />
                  ))
                )}
              </RootDropZone>
            </>
          );
        })()}

        {section === "tags" && (
          <TagBrowserSection onOpenTab={openTab} />
        )}

        {section === "skills" && (
          <SkillsSection onOpenTab={openTab} />
        )}

        {section === "settings" && (
          <div className="flex flex-col h-full">
            <div className="flex-1 overflow-auto">
              <SettingsSection onOpenVirtualTab={openVirtualTab} />
            </div>
            <UnusedImagesPanel />
          </div>
        )}
      </div>

      {/* Drag overlay */}
      <DragOverlay>
        {dragOverlay && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-background border shadow-lg text-sm opacity-90">
            {dragOverlay.is_dir
              ? <Folder className="h-3.5 w-3.5 text-muted-foreground" />
              : <File className="h-3.5 w-3.5 text-muted-foreground" />
            }
            <span>{dragOverlay.name}</span>
          </div>
        )}
      </DragOverlay>

      {/* Context Menu */}
      {contextMenu && (() => {
        const node = contextMenu.node;
        const isRoot = node === null;
        const isDir = node?.is_dir ?? false;
        const canWrite = isRoot || node?.my_permission === "write" || node?.my_permission === "manage" || !node?.my_permission;
        const canManage = isRoot || node?.my_permission === "manage" || !node?.my_permission;

        const items: MenuItemDef[] = [
          // Create actions (root or folder)
          {
            label: "새 문서",
            icon: <FilePlus className="h-3.5 w-3.5" />,
            visible: (isRoot || isDir) && canWrite,
            action: () => {
              const p = isRoot ? "__root__" : node!.path;
              setCreatingIn(p); setCreatingType("file");
              setContextMenu(null);
            },
          },
          {
            label: "새 폴더",
            icon: <FolderPlus className="h-3.5 w-3.5" />,
            visible: (isRoot || isDir) && canWrite,
            action: () => {
              const p = isRoot ? "__root__" : node!.path;
              setCreatingIn(p); setCreatingType("folder");
              setContextMenu(null);
            },
          },
          // Node-specific actions
          {
            label: "문서 링크 복사",
            icon: <Link className="h-3.5 w-3.5" />,
            visible: !isRoot,
            separator: isDir,
            action: () => { copyDocLink(node!.path); setContextMenu(null); },
          },
          {
            label: "새 버전 만들기",
            icon: <Copy className="h-3.5 w-3.5" />,
            visible: !isRoot && !isDir && canWrite && node!.path.endsWith(".md") && deprecatedMap[node!.path] !== "deprecated",
            action: () => { handleNewVersionOpen(node!.path); setContextMenu(null); },
          },
          {
            label: "이름 변경",
            icon: <Pencil className="h-3.5 w-3.5" />,
            visible: !isRoot && canWrite,
            separator: true,
            action: () => { setRenamingNode(node!); setContextMenu(null); },
          },
          // ACL-related actions
          {
            label: "공유 설정...",
            icon: <Share2 className="h-3.5 w-3.5" />,
            visible: !isRoot && canManage,
            action: () => { setShareDialogPath(node!.path); setContextMenu(null); },
          },
          {
            label: "속성",
            icon: <Info className="h-3.5 w-3.5" />,
            visible: !isRoot,
            action: () => { setPropertiesPath(node!.path); setContextMenu(null); },
          },
          // Delete actions
          {
            label: isDir ? "폴더 삭제" : "삭제",
            icon: <Trash2 className="h-3.5 w-3.5" />,
            visible: !isRoot && canWrite,
            separator: true,
            action: () => {
              if (isDir) handleDeleteFolder(node!.path);
              else handleDeleteFile(node!.path);
              setContextMenu(null);
            },
          },
        ];

        return (
          <ACLContextMenu
            x={contextMenu.x}
            y={contextMenu.y}
            items={items}
            onClose={() => setContextMenu(null)}
          />
        );
      })()}

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteConfirm} onOpenChange={(open) => { if (!open) { setDeleteConfirm(null); setDeleteLoading(false); } }}>
        <DialogContent className="sm:max-w-sm" onKeyDown={(e) => { if (e.key === "Enter" && !deleteLoading) confirmDelete(); }}>
          <DialogHeader>
            <DialogTitle>
              {deleteConfirm?.type === "folder" ? "폴더 삭제" : "문서 삭제"}
            </DialogTitle>
            <DialogDescription>
              <span className="font-semibold text-foreground">
                {deleteConfirm?.path.split("/").pop()}
              </span>
              {deleteConfirm?.type === "folder"
                ? " 폴더를 삭제하시겠습니까? (빈 폴더만 삭제 가능)"
                : " 파일을 삭제하시겠습니까?"}
              <br />이 작업은 되돌릴 수 없습니다.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirm(null)} disabled={deleteLoading}>취소</Button>
            <Button variant="destructive" onClick={confirmDelete} disabled={deleteLoading} autoFocus>
              {deleteLoading ? "삭제 중..." : "삭제"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* New Version Dialog */}
      <Dialog open={!!newVersionTarget} onOpenChange={(open) => { if (!open) setNewVersionTarget(null); }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>새 버전 만들기</DialogTitle>
            <DialogDescription>
              {newVersionTarget?.split("/").pop()} 의 새 버전을 생성합니다. 메타데이터(domain, tags)가 자동 상속됩니다.
            </DialogDescription>
          </DialogHeader>
          <input
            value={newVersionName}
            onChange={(e) => setNewVersionName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && newVersionName.trim()) handleNewVersionSubmit(); }}
            placeholder="새 파일명.md"
            className="h-9 w-full rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            autoFocus
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setNewVersionTarget(null)}>취소</Button>
            <Button onClick={handleNewVersionSubmit} disabled={newVersionCreating || !newVersionName.trim()}>
              {newVersionCreating ? "생성 중..." : "생성"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {/* Share Dialog */}
      {shareDialogPath && (
        <ShareDialog
          path={shareDialogPath}
          onClose={() => setShareDialogPath(null)}
        />
      )}

      {/* Properties Panel */}
      {propertiesPath && (
        <PropertiesPanel
          path={propertiesPath}
          onClose={() => setPropertiesPath(null)}
          onOpenShare={() => {
            setShareDialogPath(propertiesPath);
            setPropertiesPath(null);
          }}
        />
      )}
    </DndContext>
  );
}
