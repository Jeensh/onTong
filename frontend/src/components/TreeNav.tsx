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
}: {
  state: ContextMenuState;
  onClose: () => void;
  onRename: (node: WikiTreeNode) => void;
  onDeleteFile: (path: string) => void;
  onDeleteFolder: (path: string) => void;
  onNewFileInFolder: (folderPath: string) => void;
  onNewSubfolder: (folderPath: string) => void;
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
              ? <FolderOpen className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              : <Folder className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            }
            <span className="truncate">{node.name}</span>
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
                onLoadChildren={onLoadChildren} />
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
        } ${isDragging ? "opacity-40" : ""}`}
      style={{ paddingLeft: `${indent}px` }}
    >
      <span className="w-3.5 shrink-0" />
      <File className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      <span className="truncate flex-1">{node.name}</span>
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

function TagBrowserSection({ onOpenTab }: { onOpenTab: (path: string) => void }) {
  const [data, setData] = useState<{ domains: string[]; processes: string[]; tags: string[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedDomain, setExpandedDomain] = useState<string | null>(null);
  const [expandedTag, setExpandedTag] = useState<string | null>(null);
  const [tagFiles, setTagFiles] = useState<{ tag: string; files: string[] } | null>(null);

  useEffect(() => {
    fetch("/api/metadata/tags")
      .then((r) => r.json())
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const fetchFilesByTag = useCallback(async (tag: string, field: string) => {
    if (expandedTag === `${field}:${tag}`) {
      setExpandedTag(null);
      setTagFiles(null);
      return;
    }
    try {
      const res = await fetch(`/api/metadata/files-by-tag?field=${field}&value=${encodeURIComponent(tag)}`);
      if (res.ok) {
        const files: string[] = await res.json();
        setTagFiles({ tag: `${field}:${tag}`, files });
        setExpandedTag(`${field}:${tag}`);
      }
    } catch { /* ignore */ }
  }, [expandedTag]);

  if (loading) return <div className="p-3 text-sm text-muted-foreground">태그 로딩 중...</div>;
  if (!data) return <div className="p-3 text-sm text-muted-foreground">태그 데이터 없음</div>;

  return (
    <div className="flex-1 overflow-auto text-sm">
      {/* Domains */}
      <div className="px-3 pt-3 pb-1">
        <span className="text-xs font-semibold text-muted-foreground uppercase">Domain</span>
      </div>
      {data.domains.length === 0 && <div className="px-3 text-xs text-muted-foreground">없음</div>}
      {data.domains.map((d) => (
        <div key={d}>
          <button
            onClick={() => { setExpandedDomain(expandedDomain === d ? null : d); fetchFilesByTag(d, "domain"); }}
            className="flex items-center gap-1.5 px-3 py-1 w-full hover:bg-muted/50 text-left"
          >
            {expandedDomain === d ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            <span className="text-xs font-medium">{d}</span>
          </button>
          {expandedTag === `domain:${d}` && tagFiles && (
            <div className="pl-7">
              {tagFiles.files.map((f) => (
                <button key={f} onClick={() => onOpenTab(f)}
                  className="block w-full text-left px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/50 truncate">
                  {f}
                </button>
              ))}
            </div>
          )}
        </div>
      ))}

      {/* Processes */}
      <div className="px-3 pt-3 pb-1">
        <span className="text-xs font-semibold text-muted-foreground uppercase">Process</span>
      </div>
      {data.processes.length === 0 && <div className="px-3 text-xs text-muted-foreground">없음</div>}
      {data.processes.map((p) => (
        <button key={p} onClick={() => fetchFilesByTag(p, "process")}
          className="flex items-center gap-1.5 px-3 py-1 w-full hover:bg-muted/50 text-left">
          {expandedTag === `process:${p}` ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          <span className="text-xs">{p}</span>
        </button>
      ))}
      {data.processes.map((p) => (
        expandedTag === `process:${p}` && tagFiles ? (
          <div key={`files-${p}`} className="pl-7">
            {tagFiles.files.map((f) => (
              <button key={f} onClick={() => onOpenTab(f)}
                className="block w-full text-left px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/50 truncate">
                {f}
              </button>
            ))}
          </div>
        ) : null
      ))}

      {/* Tags */}
      <div className="px-3 pt-3 pb-1">
        <span className="text-xs font-semibold text-muted-foreground uppercase">Tags</span>
      </div>
      {data.tags.length === 0 && <div className="px-3 text-xs text-muted-foreground">없음</div>}
      <div className="px-3 flex flex-wrap gap-1 pb-3">
        {data.tags.map((t) => (
          <button key={t} onClick={() => fetchFilesByTag(t, "tags")}
            className={`px-1.5 py-0.5 text-xs rounded border transition-colors ${
              expandedTag === `tags:${t}` ? "bg-primary/15 border-primary/30 text-foreground" : "border-border text-muted-foreground hover:bg-muted"
            }`}>
            {t}
          </button>
        ))}
      </div>
      {expandedTag?.startsWith("tags:") && tagFiles && (
        <div className="px-3 pb-3">
          {tagFiles.files.map((f) => (
            <button key={f} onClick={() => onOpenTab(f)}
              className="block w-full text-left px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/50 truncate">
              {f}
            </button>
          ))}
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
        !showCreate && <div className="px-3 py-2 text-xs text-muted-foreground">
          {searchQuery ? "검색 결과 없음" : "스킬이 없습니다"}
        </div>
      )}

      {/* Shared skills */}
      <div className="px-3 pt-3 pb-1">
        <span className="text-xs font-semibold text-muted-foreground uppercase">공용 스킬</span>
      </div>
      {systemFiltered.length > 0 ? (
        renderGroups(systemGroups)
      ) : (
        <div className="px-3 py-2 text-xs text-muted-foreground">
          {searchQuery ? "검색 결과 없음" : "공용 스킬이 없습니다"}
        </div>
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
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>스킬 삭제</DialogTitle>
            <DialogDescription>
              <span className="font-semibold text-foreground">{deleteTarget?.title}</span> 스킬을 삭제하시겠습니까?
              <br />이 작업은 되돌릴 수 없습니다.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>취소</Button>
            <Button variant="destructive" onClick={confirmDeleteSkill}>삭제</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ── Settings Section ─────────────────────────────────────────────────

function SettingsSection({ onOpenVirtualTab }: { onOpenVirtualTab: (tabType: import("@/types").VirtualTabType) => void }) {
  return (
    <div className="flex-1 overflow-auto text-sm">
      <div className="px-3 pt-3 pb-2">
        <span className="text-xs font-semibold text-muted-foreground uppercase">관리</span>
      </div>
      <button
        onClick={() => onOpenVirtualTab("metadata-templates")}
        className="flex items-center gap-2 px-3 py-2 w-full hover:bg-muted/50 text-left"
      >
        <Tags className="h-4 w-4 text-muted-foreground" />
        <div>
          <div className="text-xs font-medium">메타데이터 템플릿</div>
          <div className="text-[11px] text-muted-foreground">Domain, Process, Tags 관리</div>
        </div>
      </button>
      <button
        onClick={() => onOpenVirtualTab("untagged-dashboard")}
        className="flex items-center gap-2 px-3 py-2 w-full hover:bg-muted/50 text-left"
      >
        <File className="h-4 w-4 text-muted-foreground" />
        <div>
          <div className="text-xs font-medium">미태깅 문서</div>
          <div className="text-[11px] text-muted-foreground">태그 없는 문서 목록 + 일괄 태깅</div>
        </div>
      </button>
      <button
        onClick={() => onOpenVirtualTab("conflict-dashboard")}
        className="flex items-center gap-2 px-3 py-2 w-full hover:bg-muted/50 text-left"
      >
        <AlertTriangle className="h-4 w-4 text-amber-500" />
        <div>
          <div className="text-xs font-medium">문서 충돌 감지</div>
          <div className="text-[11px] text-muted-foreground">유사/중복 문서 탐지 + 비교</div>
        </div>
      </button>
      <button
        onClick={() => onOpenVirtualTab("document-graph")}
        className="flex items-center gap-2 px-3 py-2 w-full hover:bg-muted/50 text-left"
      >
        <Network className="h-4 w-4 text-indigo-500" />
        <div>
          <div className="text-xs font-medium">문서 관계 그래프</div>
          <div className="text-[11px] text-muted-foreground">문서 간 연결 관계 시각화</div>
        </div>
      </button>
      <button
        onClick={() => onOpenVirtualTab("permission-editor")}
        className="flex items-center gap-2 px-3 py-2 w-full hover:bg-muted/50 text-left"
      >
        <Shield className="h-4 w-4 text-rose-500" />
        <div>
          <div className="text-xs font-medium">접근 권한 관리</div>
          <div className="text-[11px] text-muted-foreground">폴더/문서별 읽기·쓰기 제어</div>
        </div>
      </button>
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

  const handleDeleteFile = useCallback(async (path: string) => {
    const name = path.split("/").pop() ?? path;
    if (!confirm(`"${name}" 파일을 삭제하시겠습니까?`)) return;
    try {
      const res = await fetch(`/api/wiki/file/${encodeURIComponent(path)}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const tab = tabs.find((t) => t.filePath === path);
      if (tab) closeTabById(tab.id);
      toast.success(`"${name}" 삭제됨`);
      setTree((prev) => removeTreeNode(prev, path));
    } catch (err) {
      toast.error(`삭제 실패: ${(err as Error).message}`);
    }
  }, [tabs, closeTabById]);

  const handleDeleteFolder = useCallback(async (path: string) => {
    const name = path.split("/").pop() ?? path;
    if (!confirm(`"${name}" 폴더를 삭제하시겠습니까?\n(빈 폴더만 삭제 가능)`)) return;
    try {
      const res = await fetch(`/api/wiki/folder/${encodeURIComponent(path)}`, { method: "DELETE" });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${res.status}`);
      }
      toast.success(`"${name}" 폴더 삭제됨`);
      setTree((prev) => removeTreeNode(prev, path));
    } catch (err) {
      toast.error(`폴더 삭제 실패: ${(err as Error).message}`);
    }
  }, []);

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

  // ── Render ──────────────────────────────────────────────────────

  if (loading) return <div className="p-3 text-sm text-muted-foreground">불러오는 중...</div>;
  if (error) return <div className="p-3 text-sm text-destructive">트리 로드 실패: {error}</div>;

  const sectionBtnClass = (s: SidebarSection) =>
    `p-1.5 rounded transition-colors ${section === s ? "bg-primary/15 text-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`;

  return (
    <DndContext
      sensors={sensors}
      onDragStart={(e) => setDragOverlay((e.active.data.current as { node: WikiTreeNode }).node)}
      onDragEnd={handleDragEnd}
      onDragCancel={() => setDragOverlay(null)}
    >
      <div className="flex flex-col h-full">
        {/* Header with section tabs */}
        <div className="flex items-center px-3 py-2 border-b shrink-0">
          <div className="flex items-center gap-1 flex-1">
            <button onClick={() => setSection("files")} className={sectionBtnClass("files")} title="파일 트리">
              <FolderTree className="h-3.5 w-3.5" />
            </button>
            <button onClick={() => setSection("tags")} className={sectionBtnClass("tags")} title="태그 브라우저">
              <Tags className="h-3.5 w-3.5" />
            </button>
            <button onClick={() => setSection("skills")} className={sectionBtnClass("skills")} title="스킬">
              <Zap className="h-3.5 w-3.5" />
            </button>
            <button onClick={() => setSection("settings")} className={sectionBtnClass("settings")} title="관리">
              <Settings className="h-3.5 w-3.5" />
            </button>
          </div>
          <button onClick={() => openSearch(true)}
            className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground mr-1" title="문서 검색 (Ctrl+K)">
            <Search className="h-3.5 w-3.5" />
          </button>
          {section === "files" && (
            <div className="flex items-center gap-0.5">
              <button onClick={() => { setCreatingIn("__root__"); setCreatingType("file"); }}
                className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground" title="새 문서">
                <FilePlus className="h-3.5 w-3.5" />
              </button>
              <button onClick={() => { setCreatingIn("__root__"); setCreatingType("folder"); }}
                className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground" title="새 폴더">
                <FolderPlus className="h-3.5 w-3.5" />
              </button>
              <button onClick={fetchTreeData}
                className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground" title="새로고침">
                <RefreshCw className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>

        {/* Section content */}
        {section === "files" && (
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
              {tree.length === 0 && !creatingIn
                ? <div className="p-3 text-sm text-muted-foreground">파일이 없습니다</div>
                : tree.map((node) => (
                    <DraggableTreeItem key={node.path} node={node} depth={0}
                      renamingPath={renamingNode?.path ?? null}
                      activeFilePath={activeFilePath}
                      onRenameSubmit={handleRenameSubmit} onRenameCancel={() => setRenamingNode(null)}
                      onContextMenu={handleContextMenu} onOpenTab={openTab}
                      creatingIn={creatingIn} creatingType={creatingType}
                      onCreateSubmit={handleCreateSubmit}
                      onCreateCancel={() => { setCreatingIn(null); setCreatingType(null); }}
                      onLoadChildren={loadChildren} />
                  ))
              }
            </RootDropZone>
            <UnusedImagesPanel />
          </>
        )}

        {section === "tags" && (
          <TagBrowserSection onOpenTab={openTab} />
        )}

        {section === "skills" && (
          <SkillsSection onOpenTab={openTab} />
        )}

        {section === "settings" && (
          <SettingsSection onOpenVirtualTab={openVirtualTab} />
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
      {contextMenu && (
        <ContextMenu
          state={contextMenu}
          onClose={() => setContextMenu(null)}
          onRename={(node) => setRenamingNode(node)}
          onDeleteFile={handleDeleteFile}
          onDeleteFolder={handleDeleteFolder}
          onNewFileInFolder={(p) => { setCreatingIn(p); setCreatingType("file"); }}
          onNewSubfolder={(p) => { setCreatingIn(p); setCreatingType("folder"); }}
        />
      )}
    </DndContext>
  );
}
