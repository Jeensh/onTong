"use client";

/**
 * source_locations / direct_impact.methods 같은 코드 location list 를
 * 디렉토리 트리 형태로 그룹화 + method 매핑 표시.
 *
 * "필요한 파일들 연관 구조나 스캔된 부분" 시각화.
 */

import { useState, useMemo } from "react";
import { ChevronRight, ChevronDown, FileCode2, Folder, FolderOpen, Layers } from "lucide-react";

interface SourceLocation {
  class_name?: string;
  method_name?: string;
  file_path?: string;
  step_number?: number;
  [k: string]: unknown;
}

interface MethodLocation {
  class?: string;
  name?: string;
  [k: string]: unknown;
}

interface Props {
  /** source_locations (explain 응답) */
  sources?: SourceLocation[];
  /** direct_impact.methods (impact_analysis 응답) */
  methods?: MethodLocation[];
  /** 강조할 method (예: 변경 대상) */
  highlightMethod?: string;
}

interface TreeNode {
  name: string;
  type: "dir" | "file" | "class" | "method";
  children: TreeNode[];
  data?: {
    file_path?: string;
    step_number?: number;
    class_name?: string;
    method_name?: string;
  };
}

export function FileTreeView({ sources, methods, highlightMethod }: Props) {
  const tree = useMemo(() => buildTree(sources, methods), [sources, methods]);
  const total = (sources?.length ?? 0) + (methods?.length ?? 0);

  if (total === 0) {
    return <div className="text-xs text-muted-foreground italic">스캔된 코드 위치 없음.</div>;
  }

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="px-3 py-2 bg-muted/40 border-b border-border flex items-center gap-2 text-[11px]">
        <Layers size={12} className="text-primary" />
        <span className="font-semibold">스캔된 코드</span>
        <span className="text-muted-foreground">
          {tree.length} 모듈 · {countLeaves(tree)} 항목
        </span>
      </div>
      <div className="p-2 max-h-96 overflow-y-auto">
        {tree.map((n, i) => (
          <TreeNodeView key={i} node={n} depth={0} highlight={highlightMethod} />
        ))}
      </div>
    </div>
  );
}

function TreeNodeView({ node, depth, highlight }: { node: TreeNode; depth: number; highlight?: string }) {
  const [open, setOpen] = useState(depth < 2);
  const indent = depth * 12;
  const isHighlighted = highlight && node.data?.method_name === highlight;

  if (node.type === "method") {
    return (
      <div
        style={{ paddingLeft: indent + 8 }}
        className={`flex items-center gap-1.5 py-0.5 text-[11px] ${isHighlighted ? "bg-yellow-100 dark:bg-yellow-900/30 rounded font-semibold" : ""}`}
      >
        <FileCode2 size={11} className="text-emerald-600 flex-shrink-0" />
        <span className="font-mono">{node.name}</span>
        {node.data?.step_number !== undefined && (
          <span className="text-[9px] bg-blue-100 text-blue-700 px-1 py-0 rounded">Step {node.data.step_number}</span>
        )}
      </div>
    );
  }

  if (node.type === "class") {
    return (
      <div>
        <button
          onClick={() => setOpen(!open)}
          style={{ paddingLeft: indent }}
          className="w-full text-left flex items-center gap-1 py-0.5 hover:bg-muted/40 rounded text-[11px]"
        >
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          <FileCode2 size={12} className="text-cyan-600" />
          <span className="font-semibold">{node.name}</span>
          <span className="text-[9px] text-muted-foreground">({node.children.length})</span>
        </button>
        {open && node.children.map((c, i) => <TreeNodeView key={i} node={c} depth={depth + 1} highlight={highlight} />)}
      </div>
    );
  }

  // dir
  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        style={{ paddingLeft: indent }}
        className="w-full text-left flex items-center gap-1 py-0.5 hover:bg-muted/40 rounded text-[11px]"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        {open ? <FolderOpen size={12} className="text-amber-600" /> : <Folder size={12} className="text-amber-600" />}
        <span className="font-mono text-muted-foreground">{node.name}</span>
        <span className="text-[9px] text-muted-foreground">({countLeaves(node.children)})</span>
      </button>
      {open && node.children.map((c, i) => <TreeNodeView key={i} node={c} depth={depth + 1} highlight={highlight} />)}
    </div>
  );
}

function buildTree(sources?: SourceLocation[], methods?: MethodLocation[]): TreeNode[] {
  // sources 우선 — file_path 기반 디렉토리 트리
  const dirMap = new Map<string, TreeNode>();
  const classMap = new Map<string, TreeNode>();

  if (sources && sources.length > 0) {
    for (const s of sources) {
      const path = s.file_path ?? "(unknown)";
      // Java 표준 경로 — src/main/java/com/.../Foo.java
      const parts = path.split("/");
      const file = parts[parts.length - 1];
      const dir = parts.slice(0, -1).filter((p) => !["src", "main", "java", "sample-repos"].includes(p)).join("/");
      const dirKey = dir || "(root)";

      let dirNode = dirMap.get(dirKey);
      if (!dirNode) {
        dirNode = { name: dirKey || "(root)", type: "dir", children: [] };
        dirMap.set(dirKey, dirNode);
      }

      const className = s.class_name ?? file.replace(".java", "");
      const classKey = `${dirKey}::${className}`;
      let classNode = classMap.get(classKey);
      if (!classNode) {
        classNode = {
          name: className,
          type: "class",
          children: [],
          data: { file_path: path, class_name: className },
        };
        classMap.set(classKey, classNode);
        dirNode.children.push(classNode);
      }

      if (s.method_name) {
        classNode.children.push({
          name: s.method_name + "()",
          type: "method",
          children: [],
          data: { method_name: s.method_name, step_number: s.step_number },
        });
      }
    }
  } else if (methods && methods.length > 0) {
    // file_path 없을 때 — class.name 만으로 트리
    for (const m of methods) {
      const className = m.class ?? "(unknown)";
      const classKey = className;
      let classNode = classMap.get(classKey);
      if (!classNode) {
        classNode = { name: className, type: "class", children: [], data: { class_name: className } };
        classMap.set(classKey, classNode);
      }
      if (m.name) {
        classNode.children.push({
          name: m.name + "()",
          type: "method",
          children: [],
          data: { method_name: m.name },
        });
      }
    }
    // class 들을 single root 로
    return Array.from(classMap.values());
  }

  return Array.from(dirMap.values());
}

function countLeaves(nodes: TreeNode[]): number {
  return nodes.reduce((sum, n) => sum + (n.type === "method" ? 1 : countLeaves(n.children)), 0);
}
