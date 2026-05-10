"use client";

/**
 * Lightweight Java syntax highlighter (IntelliJ-ish 색상).
 *
 * 의존성 0. monaco / prism 없이 brittle-but-fast 토크나이저로 전체 body 토크나이즈 후
 * 각 token 에 CSS class 적용. 8~50 줄 method body 에 적합.
 */

import React from "react";
import { cn } from "@/lib/utils";

const KEYWORDS = new Set([
  "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char",
  "class", "const", "continue", "default", "do", "double", "else", "enum",
  "extends", "final", "finally", "float", "for", "goto", "if", "implements",
  "import", "instanceof", "int", "interface", "long", "native", "new", "null",
  "package", "private", "protected", "public", "return", "short", "static",
  "strictfp", "super", "switch", "synchronized", "this", "throw", "throws",
  "transient", "try", "void", "volatile", "while", "true", "false", "var",
  "yield", "record", "sealed", "permits", "non-sealed",
]);

type TokenKind =
  | "keyword" | "string" | "char" | "comment" | "annotation"
  | "number" | "type" | "method" | "ident" | "punct" | "ws";

interface Token { kind: TokenKind; text: string; }

/** body 한 덩어리를 토큰 배열로. 단순화 — 다중 라인 comment 도 1 token. */
function tokenize(src: string): Token[] {
  const out: Token[] = [];
  let i = 0;
  const n = src.length;
  while (i < n) {
    const ch = src[i];

    // 공백 + 줄바꿈
    if (ch === " " || ch === "\t" || ch === "\n" || ch === "\r") {
      let j = i + 1;
      while (j < n && /[ \t\n\r]/.test(src[j])) j++;
      out.push({ kind: "ws", text: src.slice(i, j) });
      i = j; continue;
    }

    // 라인 주석 //
    if (ch === "/" && src[i + 1] === "/") {
      let j = i + 2;
      while (j < n && src[j] !== "\n") j++;
      out.push({ kind: "comment", text: src.slice(i, j) });
      i = j; continue;
    }

    // 블록 주석 /* ... */
    if (ch === "/" && src[i + 1] === "*") {
      let j = i + 2;
      while (j < n && !(src[j] === "*" && src[j + 1] === "/")) j++;
      j = Math.min(j + 2, n);
      out.push({ kind: "comment", text: src.slice(i, j) });
      i = j; continue;
    }

    // 문자열 literal "..."
    if (ch === '"') {
      let j = i + 1;
      while (j < n && src[j] !== '"') {
        if (src[j] === "\\" && j + 1 < n) j++;
        j++;
      }
      j = Math.min(j + 1, n);
      out.push({ kind: "string", text: src.slice(i, j) });
      i = j; continue;
    }

    // char literal '...'
    if (ch === "'") {
      let j = i + 1;
      while (j < n && src[j] !== "'") {
        if (src[j] === "\\" && j + 1 < n) j++;
        j++;
      }
      j = Math.min(j + 1, n);
      out.push({ kind: "char", text: src.slice(i, j) });
      i = j; continue;
    }

    // 어노테이션 @Foo
    if (ch === "@" && /[A-Za-z_]/.test(src[i + 1] ?? "")) {
      let j = i + 1;
      while (j < n && /[A-Za-z0-9_]/.test(src[j])) j++;
      out.push({ kind: "annotation", text: src.slice(i, j) });
      i = j; continue;
    }

    // 숫자 (정수 / 실수 / hex / suffix)
    if (/[0-9]/.test(ch)) {
      let j = i + 1;
      while (j < n && /[0-9._eExXfFlLdDbBoO]/.test(src[j])) j++;
      out.push({ kind: "number", text: src.slice(i, j) });
      i = j; continue;
    }

    // 식별자 / 키워드
    if (/[A-Za-z_$]/.test(ch)) {
      let j = i + 1;
      while (j < n && /[A-Za-z0-9_$]/.test(src[j])) j++;
      const word = src.slice(i, j);
      let kind: TokenKind;
      if (KEYWORDS.has(word)) kind = "keyword";
      else if (/^[A-Z]/.test(word)) kind = "type";   // 대문자 시작 = 타입 추정
      else {
        // method 호출 패턴: 다음 non-ws 가 ( 면 method
        let k = j;
        while (k < n && /[ \t]/.test(src[k])) k++;
        kind = (src[k] === "(") ? "method" : "ident";
      }
      out.push({ kind, text: word });
      i = j; continue;
    }

    // 그 외 = punct/op 1글자
    out.push({ kind: "punct", text: ch });
    i += 1;
  }
  return out;
}

/** 토큰을 line 별로 분리 (개행 보존) — 라인 단위 render 용. */
function tokensByLine(tokens: Token[]): Token[][] {
  const lines: Token[][] = [[]];
  for (const t of tokens) {
    if (t.kind === "ws" && t.text.includes("\n")) {
      // ws 안에 \n 들어있으면 line 경계로 split
      const parts = t.text.split("\n");
      for (let i = 0; i < parts.length; i++) {
        if (parts[i]) lines[lines.length - 1].push({ kind: "ws", text: parts[i] });
        if (i < parts.length - 1) lines.push([]);   // 새 라인
      }
    } else {
      lines[lines.length - 1].push(t);
    }
  }
  return lines;
}

const TOKEN_CLASS: Record<TokenKind, string> = {
  keyword:    "text-violet-700 font-semibold",
  type:       "text-emerald-700",
  string:     "text-emerald-600",
  char:       "text-emerald-600",
  number:     "text-amber-700",
  comment:    "text-muted-foreground italic",
  annotation: "text-amber-700",
  method:     "text-sky-700",
  ident:      "text-foreground",
  punct:      "text-muted-foreground",
  ws:         "",
};

export interface JavaCodeProps {
  source: string;
  startLine?: number;
  /** 어떤 라인에 marker 표시할지 (anchor 등). lineNo → label 또는 React node. */
  markers?: Map<number, { label: string; tone: "semantic" | "static" | "info" }>;
  /** 호버 line — 외부 sync. */
  hoverLine?: number | null;
  setHoverLine?: (n: number | null) => void;
  className?: string;
  showLineNumbers?: boolean;
}

export function JavaCode({
  source,
  startLine = 1,
  markers,
  hoverLine,
  setHoverLine,
  className,
  showLineNumbers = true,
}: JavaCodeProps) {
  const tokens = React.useMemo(() => tokenize(source), [source]);
  const lines = React.useMemo(() => tokensByLine(tokens), [tokens]);

  return (
    <div className={cn("font-mono text-[12px] leading-relaxed", className)}>
      {lines.map((lineTokens, idx) => {
        const lineNo = startLine + idx;
        const marker = markers?.get(lineNo);
        const isHover = hoverLine === lineNo;
        return (
          <div
            key={idx}
            onMouseEnter={() => marker && setHoverLine?.(lineNo)}
            onMouseLeave={() => isHover && setHoverLine?.(null)}
            className={cn(
              "grid gap-1 px-3 transition-colors",
              showLineNumbers ? "grid-cols-[40px_20px_1fr]" : "grid-cols-[20px_1fr]",
              isHover && "bg-sky-100",
              !isHover && marker?.tone === "semantic" && "bg-sky-50/60",
              !isHover && marker?.tone === "static" && "bg-amber-50/30",
            )}
            title={marker?.label}
          >
            {showLineNumbers && (
              <span className="text-right text-muted-foreground select-none">{lineNo}</span>
            )}
            <span className="text-center select-none text-[11px]">
              {marker?.tone === "semantic" ? <span className="text-sky-600 font-bold">A</span>
                : marker?.tone === "static" ? <span className="text-amber-600">·</span>
                : marker?.tone === "info" ? <span className="text-emerald-600">i</span>
                : ""}
            </span>
            <span className="whitespace-pre-wrap break-all">
              {lineTokens.length === 0 ? " " : lineTokens.map((t, ti) => (
                <span key={ti} className={TOKEN_CLASS[t.kind]}>{t.text}</span>
              ))}
            </span>
          </div>
        );
      })}
    </div>
  );
}
