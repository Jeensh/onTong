"use client";

import { useState, useRef, useEffect } from "react";
import { X, Plus, FileText } from "lucide-react";

interface SearchResult {
  path: string;
  title: string;
  snippet: string;
  score: number;
}

interface ReferencedDocsPickerProps {
  value: string[];
  onChange: (docs: string[]) => void;
}

export function ReferencedDocsPicker({ value, onChange }: ReferencedDocsPickerProps) {
  const [showSearch, setShowSearch] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    if (showSearch) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [showSearch]);

  const search = (q: string) => {
    setQuery(q);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q.trim()) { setResults([]); return; }

    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/search/quick?q=${encodeURIComponent(q)}&limit=10`);
        if (res.ok) {
          const data: SearchResult[] = await res.json();
          // Filter out already-selected docs and skill files
          setResults(data.filter((r) => !r.path.startsWith("_skills/") && !value.includes(r.path)));
        }
      } catch { /* ignore */ }
      setLoading(false);
    }, 300);
  };

  const addDoc = (path: string) => {
    if (!value.includes(path)) {
      onChange([...value, path]);
    }
    setQuery("");
    setResults([]);
    setShowSearch(false);
  };

  const removeDoc = (path: string) => {
    onChange(value.filter((d) => d !== path));
  };

  const displayName = (path: string) => {
    const name = path.replace(/\.md$/, "");
    const parts = name.split("/");
    return parts[parts.length - 1];
  };

  return (
    <div className="space-y-1.5">
      {/* Selected docs */}
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {value.map((doc) => (
            <span
              key={doc}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-muted text-xs"
              title={doc}
            >
              <FileText className="h-3 w-3 text-muted-foreground" />
              {displayName(doc)}
              <button
                type="button"
                onClick={() => removeDoc(doc)}
                className="hover:text-destructive"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Search input */}
      {showSearch ? (
        <div className="relative">
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => search(e.target.value)}
            placeholder="문서 검색..."
            className="w-full text-xs px-2 py-1 rounded border bg-background"
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                setShowSearch(false);
                setQuery("");
                setResults([]);
              }
            }}
          />
          {loading && (
            <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
              ...
            </span>
          )}
          {results.length > 0 && (
            <div className="absolute z-50 top-full left-0 right-0 mt-1 max-h-40 overflow-auto rounded border bg-popover shadow-md">
              {results.map((r) => (
                <button
                  key={r.path}
                  type="button"
                  onClick={() => addDoc(r.path)}
                  className="w-full text-left px-2 py-1.5 text-xs hover:bg-muted flex items-center gap-2"
                >
                  <FileText className="h-3 w-3 text-muted-foreground shrink-0" />
                  <span className="truncate font-medium">{r.title || displayName(r.path)}</span>
                  <span className="text-muted-foreground truncate ml-auto text-[10px]">{r.path}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setShowSearch(true)}
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <Plus className="h-3 w-3" />
          참조 문서 추가
        </button>
      )}
    </div>
  );
}
