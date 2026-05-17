"use client";

/**
 * 가벼운 syntax highlighter — 외부 lib 없이 정규식 기반.
 * python / cypher / json 지원.
 */

import { useState } from "react";
import { Copy, Check } from "lucide-react";

interface Props {
  code: string;
  language?: "python" | "cypher" | "json" | "text";
  filename?: string;
  maxHeight?: number;
  showLineNumbers?: boolean;
}

export function CodeBlock({ code, language = "text", filename, maxHeight = 360, showLineNumbers = true }: Props) {
  const [copied, setCopied] = useState(false);
  const lines = code.split("\n");

  const copy = () => {
    navigator.clipboard?.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="rounded-lg overflow-hidden border border-slate-700 bg-slate-900 text-slate-100">
      <div className="flex items-center justify-between px-3 py-1.5 bg-slate-800 border-b border-slate-700">
        <div className="flex items-center gap-2 text-[10px]">
          <LangPill language={language} />
          {filename && <span className="text-slate-400 font-mono">{filename}</span>}
          <span className="text-slate-500">· {lines.length} 줄</span>
        </div>
        <button
          onClick={copy}
          className="inline-flex items-center gap-1 text-[10px] text-slate-400 hover:text-slate-100 px-2 py-0.5 rounded hover:bg-slate-700 transition-colors"
        >
          {copied ? <><Check size={11} /> 복사됨</> : <><Copy size={11} /> 복사</>}
        </button>
      </div>
      <div className="overflow-auto" style={{ maxHeight }}>
        <pre className="text-[11px] leading-relaxed font-mono">
          {lines.map((line, i) => (
            <div key={i} className="flex hover:bg-slate-800/50 px-3">
              {showLineNumbers && (
                <span className="select-none text-slate-600 mr-3 text-right w-7 flex-shrink-0">{i + 1}</span>
              )}
              <span className="flex-1 whitespace-pre-wrap break-all">{highlight(line, language)}</span>
            </div>
          ))}
        </pre>
      </div>
    </div>
  );
}

function LangPill({ language }: { language: string }) {
  const tone: Record<string, string> = {
    python: "bg-blue-500/20 text-blue-300 border-blue-500/30",
    cypher: "bg-purple-500/20 text-purple-300 border-purple-500/30",
    json: "bg-amber-500/20 text-amber-300 border-amber-500/30",
    text: "bg-slate-600/30 text-slate-300 border-slate-600/40",
  };
  return (
    <span className={`px-1.5 py-0.5 rounded border ${tone[language] || tone.text} font-mono uppercase`}>{language}</span>
  );
}

// ─── 가벼운 syntax highlight (정규식) ─────────────────────

const PY_KEYWORDS = new Set([
  "def", "return", "if", "elif", "else", "for", "while", "import", "from", "as", "in",
  "is", "not", "and", "or", "None", "True", "False", "class", "try", "except", "finally",
  "with", "lambda", "yield", "pass", "break", "continue", "raise",
]);
const CYPHER_KEYWORDS = new Set([
  "MATCH", "OPTIONAL", "WHERE", "RETURN", "WITH", "AS", "ORDER", "BY", "LIMIT", "SKIP",
  "CREATE", "MERGE", "DELETE", "DETACH", "SET", "REMOVE", "UNION", "AND", "OR", "NOT",
  "IN", "IS", "NULL", "TRUE", "FALSE", "COLLECT", "DISTINCT", "COUNT",
]);

function highlight(line: string, language: string): React.ReactNode {
  if (language === "text") return line || " ";

  const parts: React.ReactNode[] = [];
  // strings
  const stringRe = /("[^"]*"|'[^']*'|`[^`]*`)/g;
  let lastIdx = 0;
  let m;
  while ((m = stringRe.exec(line)) !== null) {
    if (m.index > lastIdx) parts.push(tokenize(line.slice(lastIdx, m.index), language));
    parts.push(<span key={`s${m.index}`} className="text-emerald-300">{m[0]}</span>);
    lastIdx = m.index + m[0].length;
  }
  if (lastIdx < line.length) parts.push(tokenize(line.slice(lastIdx), language));
  if (parts.length === 0) return line || " ";
  return <>{parts}</>;
}

function tokenize(s: string, language: string): React.ReactNode {
  // comments
  const commentRe = language === "python" ? /(#.*)$/ : language === "cypher" ? /(\/\/.*)$/ : null;
  if (commentRe) {
    const cm = s.match(commentRe);
    if (cm) {
      const before = s.slice(0, cm.index);
      return <>{tokenizeWords(before, language)}<span className="text-slate-500 italic">{cm[0]}</span></>;
    }
  }
  return tokenizeWords(s, language);
}

function tokenizeWords(s: string, language: string): React.ReactNode {
  const KW = language === "python" ? PY_KEYWORDS : language === "cypher" ? CYPHER_KEYWORDS : new Set<string>();
  const parts: React.ReactNode[] = [];
  const re = /[A-Za-z_][A-Za-z0-9_]*|\d+\.?\d*|[^A-Za-z0-9_]+/g;
  let m;
  let key = 0;
  while ((m = re.exec(s)) !== null) {
    const w = m[0];
    if (KW.has(w) || (language === "cypher" && KW.has(w.toUpperCase()))) {
      parts.push(<span key={key++} className="text-purple-300 font-semibold">{w}</span>);
    } else if (/^\d/.test(w)) {
      parts.push(<span key={key++} className="text-amber-300">{w}</span>);
    } else if (/^[a-z_]/.test(w) && w.length > 0 && language === "python") {
      // function call?
      const next = s[m.index + w.length];
      if (next === "(") {
        parts.push(<span key={key++} className="text-cyan-300">{w}</span>);
      } else {
        parts.push(w);
      }
    } else {
      parts.push(w);
    }
  }
  return <>{parts}</>;
}
