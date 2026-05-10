"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { searchTerms, type TermSearchResult } from "@/lib/simulation/agentApi";

export interface EntityOption {
  id: string;
  label: string;
  category?: string;
  hint?: string;
}

interface EntitySearchBoxProps {
  /** 입력 값 (controlled). */
  value: string;
  /** 입력 변경 시. */
  onChange: (value: string) => void;
  /** 항목 선택 시. (id가 form 제출 값) */
  onSelect: (option: EntityOption) => void;
  /** 자동완성 모드:
   *  - "term": Section 2 term/search API 호출 (Agent 3 자연어 보조용)
   *  - "static": props로 전달된 options 안에서 client-side 필터
   */
  mode?: "term" | "static";
  /** static 모드에서 사용할 후보 목록. */
  options?: EntityOption[];
  placeholder?: string;
  disabled?: boolean;
}

export function EntitySearchBox({
  value,
  onChange,
  onSelect,
  mode = "static",
  options = [],
  placeholder = "검색...",
  disabled,
}: EntitySearchBoxProps) {
  const [open, setOpen] = useState(false);
  const [remote, setRemote] = useState<TermSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  // term 모드: 디바운스된 원격 검색
  useEffect(() => {
    if (mode !== "term") return;
    if (!value.trim()) {
      setRemote([]);
      return;
    }
    const t = setTimeout(() => {
      setLoading(true);
      searchTerms(value, 8)
        .then(setRemote)
        .catch(() => setRemote([]))
        .finally(() => setLoading(false));
    }, 200);
    return () => clearTimeout(t);
  }, [value, mode]);

  // 외부 클릭으로 닫기
  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  const items: EntityOption[] = useMemo(() => {
    if (mode === "term") {
      return remote.map((t) => ({
        id: t.id,
        label: `${t.name} (${t.english})`,
        category: t.category,
        hint: t.description,
      }));
    }
    const q = value.toLowerCase();
    return options.filter(
      (o) =>
        !q ||
        o.id.toLowerCase().includes(q) ||
        o.label.toLowerCase().includes(q)
    );
  }, [mode, remote, options, value]);

  return (
    <div ref={wrapRef} className="relative">
      <input
        type="text"
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder={placeholder}
        disabled={disabled}
        className="w-full rounded border border-gray-300 px-3 py-2 text-sm outline-none focus:border-blue-500 disabled:bg-gray-100"
      />
      {open && (items.length > 0 || loading) && (
        <ul className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded border border-gray-200 bg-white shadow-lg">
          {loading && (
            <li className="px-3 py-2 text-sm text-gray-400">검색 중...</li>
          )}
          {items.map((opt) => (
            <li
              key={opt.id}
              className="cursor-pointer px-3 py-2 text-sm hover:bg-blue-50"
              onClick={() => {
                onSelect(opt);
                onChange(opt.label);
                setOpen(false);
              }}
            >
              <div className="font-medium">{opt.label}</div>
              <div className="flex gap-2 text-xs text-gray-500">
                <span className="font-mono">{opt.id}</span>
                {opt.category && <span>· {opt.category}</span>}
              </div>
              {opt.hint && (
                <div className="mt-0.5 text-xs text-gray-400">{opt.hint}</div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
