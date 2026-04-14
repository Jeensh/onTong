"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { X } from "lucide-react";

interface TagInputProps {
  tags: string[];
  /** Static suggestions list (used if onSearch is not provided) */
  suggestions?: string[];
  /** Async search function for lazy loading (debounced internally) */
  onSearch?: (query: string) => Promise<string[]>;
  /** Async search that returns tags with counts */
  onSearchWithCount?: (query: string) => Promise<{ name: string; count: number }[]>;
  /** Check for similar existing tags before adding a new one */
  onCheckSimilar?: (tag: string) => Promise<{ tag: string; count: number }[]>;
  onChange: (tags: string[]) => void;
  placeholder?: string;
}

export function TagInput({ tags, suggestions, onSearch, onSearchWithCount, onCheckSimilar, onChange, placeholder }: TagInputProps) {
  const [input, setInput] = useState("");
  const [showDropdown, setShowDropdown] = useState(false);
  const [searchResults, setSearchResults] = useState<string[]>([]);
  const [searchResultsWithCount, setSearchResultsWithCount] = useState<{ name: string; count: number }[]>([]);
  const [similarPrompt, setSimilarPrompt] = useState<{ tag: string; similar: { tag: string; count: number }[] } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const similarCacheRef = useRef<Map<string, { tag: string; count: number }[]>>(new Map());

  const useCountMode = !!onSearchWithCount;

  // Determine which suggestion source to use
  const filtered = useCountMode
    ? searchResultsWithCount.filter((s) => !tags.includes(s.name))
    : onSearch
    ? searchResults.filter((s) => !tags.includes(s))
    : (suggestions || []).filter(
        (s) => s.toLowerCase().includes(input.toLowerCase()) && !tags.includes(s)
      );

  // Debounced async search
  useEffect(() => {
    if ((!onSearch && !onSearchWithCount) || !input.trim()) {
      setSearchResults([]);
      setSearchResultsWithCount([]);
      return;
    }
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      const q = input.trim();
      try {
        if (onSearchWithCount) {
          const results = await onSearchWithCount(q);
          setSearchResultsWithCount(results);
        } else if (onSearch) {
          const results = await onSearch(q);
          setSearchResults(results);
        }
      } catch {
        setSearchResults([]);
        setSearchResultsWithCount([]);
      }
      // Preemptive similar check: warm the cache in background while user reads dropdown
      if (onCheckSimilar && !similarCacheRef.current.has(q)) {
        onCheckSimilar(q)
          .then((similar) => {
            const cache = similarCacheRef.current;
            cache.set(q, similar);
            while (cache.size > 50) {
              const oldest = cache.keys().next().value;
              if (oldest === undefined) break;
              cache.delete(oldest);
            }
          })
          .catch(() => {});
      }
    }, 200);
    return () => clearTimeout(debounceRef.current);
  }, [input, onSearch, onSearchWithCount]);

  const doAddTag = useCallback(
    (tag: string) => {
      const trimmed = tag.trim();
      if (!trimmed || tags.includes(trimmed)) return;
      onChange([...tags, trimmed]);
      setInput("");
      setShowDropdown(false);
      setSearchResults([]);
      setSearchResultsWithCount([]);
      setSimilarPrompt(null);
    },
    [tags, onChange]
  );

  const addTag = useCallback(
    async (tag: string) => {
      const trimmed = tag.trim();
      if (!trimmed || tags.includes(trimmed)) return;

      // Smart Friction: check for similar tags before adding
      if (onCheckSimilar) {
        // Check if this tag already exists in search results (user picked from dropdown)
        const existsInResults = useCountMode
          ? searchResultsWithCount.some((s) => s.name === trimmed)
          : searchResults.includes(trimmed);

        if (!existsInResults) {
          try {
            const cache = similarCacheRef.current;
            const cached = cache.get(trimmed);
            if (cached !== undefined) {
              // Refresh LRU recency: re-insert to move to tail
              cache.delete(trimmed);
              cache.set(trimmed, cached);
            }
            const similar = cached ?? (await onCheckSimilar(trimmed));
            if (cached === undefined) cache.set(trimmed, similar);
            if (similar.length > 0) {
              setSimilarPrompt({ tag: trimmed, similar });
              return;
            }
          } catch { /* proceed without check */ }
        }
      }

      doAddTag(trimmed);
    },
    [tags, onCheckSimilar, doAddTag, searchResults, searchResultsWithCount, useCountMode]
  );

  const removeTag = useCallback(
    (tag: string) => {
      onChange(tags.filter((t) => t !== tag));
    },
    [tags, onChange]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.nativeEvent.isComposing) return;
    if (e.key === "Enter" && input.trim()) {
      e.preventDefault();
      addTag(input);
    } else if (e.key === "Escape") {
      setShowDropdown(false);
      setSimilarPrompt(null);
    } else if (e.key === "Backspace" && !input && tags.length > 0) {
      removeTag(tags[tags.length - 1]);
    }
  };

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
        setSimilarPrompt(null);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div ref={containerRef} className="relative">
      <div className="flex flex-wrap items-center gap-1 rounded-md border border-input bg-background px-2 py-1 text-sm min-h-[32px]">
        {tags.map((tag) => (
          <Badge key={tag} variant="secondary" className="gap-1 pr-1">
            {tag}
            <button
              type="button"
              onClick={() => removeTag(tag)}
              className="ml-0.5 rounded-full hover:bg-muted-foreground/20"
            >
              <X className="h-3 w-3" />
            </button>
          </Badge>
        ))}
        <input
          ref={inputRef}
          type="text"
          className="flex-1 min-w-[80px] bg-transparent outline-none placeholder:text-muted-foreground text-sm"
          placeholder={tags.length === 0 ? (placeholder || "태그 입력...") : ""}
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
            setShowDropdown(true);
            setSimilarPrompt(null);
          }}
          onFocus={() => setShowDropdown(true)}
          onKeyDown={handleKeyDown}
        />
      </div>

      {/* Smart Friction: similar tag prompt */}
      {similarPrompt && (
        <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-md p-3">
          <p className="text-xs text-muted-foreground mb-2">
            유사한 태그가 있습니다. 기존 태그를 사용하시겠습니까?
          </p>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {similarPrompt.similar.map((s) => (
              <button
                key={s.tag}
                type="button"
                className="px-2 py-1 text-xs rounded-md border border-primary/30 bg-primary/10 text-foreground hover:bg-primary/20"
                onMouseDown={(e) => { e.preventDefault(); doAddTag(s.tag); }}
              >
                {s.tag} <span className="text-muted-foreground">({s.count}건)</span>
              </button>
            ))}
          </div>
          <button
            type="button"
            className="text-[11px] text-muted-foreground hover:text-foreground"
            onMouseDown={(e) => { e.preventDefault(); doAddTag(similarPrompt.tag); }}
          >
            그래도 &quot;{similarPrompt.tag}&quot; 생성
          </button>
        </div>
      )}

      {/* Dropdown suggestions */}
      {showDropdown && !similarPrompt && input && (
        <>
          {useCountMode && filtered.length > 0 && (
            <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-md max-h-40 overflow-auto">
              {(filtered as { name: string; count: number }[]).slice(0, 10).map((s) => (
                <button
                  key={s.name}
                  type="button"
                  className="w-full px-3 py-1.5 text-left text-sm hover:bg-accent hover:text-accent-foreground flex items-center justify-between"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    doAddTag(s.name);
                  }}
                >
                  <span>{s.name}</span>
                  <span className="text-[10px] text-muted-foreground">{s.count}건</span>
                </button>
              ))}
            </div>
          )}
          {!useCountMode && (filtered as string[]).length > 0 && (
            <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-md max-h-40 overflow-auto">
              {(filtered as string[]).slice(0, 10).map((s) => (
                <button
                  key={s}
                  type="button"
                  className="w-full px-3 py-1.5 text-left text-sm hover:bg-accent hover:text-accent-foreground"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    doAddTag(s);
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
