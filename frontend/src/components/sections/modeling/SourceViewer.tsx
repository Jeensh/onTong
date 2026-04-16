"use client";

import React, { useCallback, useEffect, useState, useRef } from "react";
import {
  ChevronRight,
  ChevronDown,
  FileCode,
  Folder,
  FolderOpen,
  Search,
} from "lucide-react";
import Editor, { type Monaco } from "@monaco-editor/react";
import type { editor as MonacoEditor } from "monaco-editor";
import {
  getSourceTree,
  getSourceFile,
  type SourceTreeNode,
  type SourceFileResponse,
} from "@/lib/api/modeling";

interface SourceViewerProps {
  repoId: string;
  highlightEntity?: string | null;
  onEntityClick?: (fqn: string, filePath: string) => void;
}

// ── File Tree ──

interface FileTreeItemProps {
  node: SourceTreeNode;
  depth: number;
  selectedPath: string | null;
  expandedDirs: Set<string>;
  onFileClick: (path: string) => void;
  onToggleDir: (path: string) => void;
  filter: string;
}

function FileTreeItem({
  node,
  depth,
  selectedPath,
  expandedDirs,
  onFileClick,
  onToggleDir,
  filter,
}: FileTreeItemProps) {
  if (filter && node.type === "file" && !node.name.toLowerCase().includes(filter.toLowerCase())) {
    return null;
  }

  const isDir = node.type === "directory";
  const isExpanded = expandedDirs.has(node.path);
  const isSelected = node.path === selectedPath;

  // For directories with filter, check if any child matches
  if (filter && isDir) {
    const hasMatch = hasMatchingChild(node, filter);
    if (!hasMatch) return null;
  }

  return (
    <>
      <button
        onClick={() => isDir ? onToggleDir(node.path) : onFileClick(node.path)}
        className={`flex items-center gap-1 w-full px-2 py-0.5 text-xs hover:bg-muted/50 rounded transition-colors ${
          isSelected ? "bg-primary/10 text-primary font-medium" : "text-foreground/80"
        }`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        {isDir ? (
          <>
            {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            {isExpanded ? <FolderOpen size={14} className="text-amber-500" /> : <Folder size={14} className="text-amber-500" />}
          </>
        ) : (
          <>
            <span style={{ width: 12 }} />
            <FileCode size={14} className="text-blue-400" />
          </>
        )}
        <span className="truncate">{node.name}</span>
      </button>
      {isDir && isExpanded && node.children?.map((child) => (
        <FileTreeItem
          key={child.path}
          node={child}
          depth={depth + 1}
          selectedPath={selectedPath}
          expandedDirs={expandedDirs}
          onFileClick={onFileClick}
          onToggleDir={onToggleDir}
          filter={filter}
        />
      ))}
    </>
  );
}

function hasMatchingChild(node: SourceTreeNode, filter: string): boolean {
  if (node.type === "file") return node.name.toLowerCase().includes(filter.toLowerCase());
  return node.children?.some((child) => hasMatchingChild(child, filter)) ?? false;
}

// ── Main Component ──

export function SourceViewer({ repoId, highlightEntity, onEntityClick }: SourceViewerProps) {
  const [tree, setTree] = useState<SourceTreeNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileData, setFileData] = useState<SourceFileResponse | null>(null);
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const editorRef = useRef<MonacoEditor.IStandaloneCodeEditor | null>(null);
  const monacoRef = useRef<Monaco | null>(null);
  const decorationsRef = useRef<string[]>([]);
  const fileDataRef = useRef<SourceFileResponse | null>(null);
  const onEntityClickRef = useRef(onEntityClick);
  onEntityClickRef.current = onEntityClick;

  // Load file tree
  useEffect(() => {
    if (!repoId) return;
    setLoading(true);
    setError(null);
    getSourceTree(repoId)
      .then((data) => {
        setTree(data);
        // Auto-expand first two levels
        const dirs = new Set<string>();
        function expandLevels(node: SourceTreeNode, depth: number) {
          if (node.type === "directory" && depth < 3) {
            dirs.add(node.path);
            node.children?.forEach((c) => expandLevels(c, depth + 1));
          }
        }
        expandLevels(data, 0);
        setExpandedDirs(dirs);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [repoId]);

  // Keep fileDataRef in sync
  useEffect(() => {
    fileDataRef.current = fileData;
  }, [fileData]);

  // Load file content
  const handleFileClick = useCallback(
    async (path: string) => {
      setSelectedFile(path);
      try {
        const data = await getSourceFile(repoId, path);
        setFileData(data);
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [repoId]
  );

  const handleToggleDir = useCallback((path: string) => {
    setExpandedDirs((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  // Highlight entity in editor
  useEffect(() => {
    if (!highlightEntity || !fileData || !editorRef.current || !monacoRef.current) return;

    const entity = fileData.entities.find((e) => e.fqn === highlightEntity);
    if (!entity) return;

    const monaco = monacoRef.current;
    const editor = editorRef.current;

    // Scroll to entity
    editor.revealLineInCenter(entity.start_line);

    // Apply decoration
    const newDecorations = editor.deltaDecorations(decorationsRef.current, [
      {
        range: new monaco.Range(entity.start_line, 1, entity.end_line, 1),
        options: {
          isWholeLine: true,
          className: "bg-primary/15",
          glyphMarginClassName: "bg-primary",
        },
      },
    ]);
    decorationsRef.current = newDecorations;
  }, [highlightEntity, fileData]);

  // Apply entity gutter markers
  useEffect(() => {
    if (!fileData || !editorRef.current || !monacoRef.current) return;
    if (highlightEntity) return; // skip if highlight is active

    const monaco = monacoRef.current;
    const editor = editorRef.current;

    const decorations = fileData.entities
      .filter((e) => e.mapping)
      .map((e) => ({
        range: new monaco.Range(e.start_line, 1, e.end_line, 1),
        options: {
          isWholeLine: true,
          linesDecorationsClassName: e.mapping?.status === "confirmed"
            ? "border-l-2 border-green-500"
            : "border-l-2 border-yellow-500",
          minimap: { color: e.mapping?.status === "confirmed" ? "#22c55e" : "#eab308", position: 1 },
        },
      }));

    const newDecorations = editor.deltaDecorations(decorationsRef.current, decorations);
    decorationsRef.current = newDecorations;
  }, [fileData, highlightEntity]);

  const handleEditorMount = useCallback(
    (editor: MonacoEditor.IStandaloneCodeEditor, monaco: Monaco) => {
      editorRef.current = editor;
      monacoRef.current = monaco;

      // Click handler: use refs to always access latest fileData/onEntityClick
      editor.onMouseDown((e) => {
        const currentFileData = fileDataRef.current;
        const currentOnEntityClick = onEntityClickRef.current;
        if (!currentFileData || !currentOnEntityClick) return;
        const lineNumber = e.target.position?.lineNumber;
        if (!lineNumber) return;

        const entity = currentFileData.entities.find(
          (ent) => lineNumber >= ent.start_line && lineNumber <= ent.end_line
        );
        if (entity && currentFileData.path) {
          currentOnEntityClick(entity.fqn, currentFileData.path);
        }
      });
    },
    []
  );

  return (
    <div className="flex flex-col h-full">
      {/* File tree header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border bg-muted/30">
        <span className="text-xs font-medium text-foreground">소스 코드</span>
        <div className="flex-1" />
        <div className="relative">
          <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="파일 검색..."
            className="pl-6 pr-2 py-0.5 text-[11px] w-32 bg-background border border-border rounded"
          />
        </div>
      </div>

      {/* File tree */}
      <div className="h-48 min-h-[120px] overflow-auto border-b border-border">
        {loading && <p className="text-xs text-muted-foreground p-3">로딩 중...</p>}
        {error && <p className="text-xs text-red-500 p-3">{error}</p>}
        {tree && (
          <div className="py-1">
            {tree.children?.map((child) => (
              <FileTreeItem
                key={child.path}
                node={child}
                depth={0}
                selectedPath={selectedFile}
                expandedDirs={expandedDirs}
                onFileClick={handleFileClick}
                onToggleDir={handleToggleDir}
                filter={filter}
              />
            ))}
          </div>
        )}
      </div>

      {/* Code display */}
      <div className="flex-1 min-h-0">
        {!fileData ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <p className="text-xs">파일을 선택하세요</p>
          </div>
        ) : (
          <div className="h-full flex flex-col">
            {/* File path bar */}
            <div className="flex items-center gap-1 px-3 py-1 bg-muted/20 border-b border-border">
              <FileCode size={12} className="text-blue-400" />
              <span className="text-[11px] text-muted-foreground font-mono truncate">{fileData.path}</span>
              {fileData.entities.length > 0 && (
                <span className="ml-auto text-[10px] text-muted-foreground">
                  {fileData.entities.length}개 엔티티
                </span>
              )}
            </div>
            <div className="flex-1 min-h-0">
              <Editor
                language={fileData.language}
                value={fileData.content}
                theme="vs-dark"
                onMount={handleEditorMount}
                options={{
                  readOnly: true,
                  minimap: { enabled: true },
                  fontSize: 13,
                  lineNumbers: "on",
                  scrollBeyondLastLine: false,
                  glyphMargin: true,
                  folding: true,
                  wordWrap: "off",
                  renderLineHighlight: "line",
                }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
