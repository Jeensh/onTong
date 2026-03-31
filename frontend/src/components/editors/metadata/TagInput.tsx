"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { X } from "lucide-react";

interface TagInputProps {
  tags: string[];
  suggestions: string[];
  onChange: (tags: string[]) => void;
}

export function TagInput({ tags, suggestions, onChange }: TagInputProps) {
  const [input, setInput] = useState("");
  const [showDropdown, setShowDropdown] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const filtered = suggestions.filter(
    (s) =>
      s.toLowerCase().includes(input.toLowerCase()) && !tags.includes(s)
  );

  const addTag = useCallback(
    (tag: string) => {
      const trimmed = tag.trim();
      if (!trimmed || tags.includes(trimmed)) return;
      onChange([...tags, trimmed]);
      setInput("");
      setShowDropdown(false);
    },
    [tags, onChange]
  );

  const removeTag = useCallback(
    (tag: string) => {
      onChange(tags.filter((t) => t !== tag));
    },
    [tags, onChange]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Skip during IME composition (Korean/Japanese/Chinese input)
    if (e.nativeEvent.isComposing) return;
    if (e.key === "Enter" && input.trim()) {
      e.preventDefault();
      addTag(input);
    } else if (e.key === "Escape") {
      setShowDropdown(false);
    } else if (e.key === "Backspace" && !input && tags.length > 0) {
      removeTag(tags[tags.length - 1]);
    }
  };

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setShowDropdown(false);
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
          placeholder={tags.length === 0 ? "태그 입력..." : ""}
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
            setShowDropdown(true);
          }}
          onFocus={() => setShowDropdown(true)}
          onKeyDown={handleKeyDown}
        />
      </div>

      {showDropdown && input && filtered.length > 0 && (
        <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-md max-h-40 overflow-auto">
          {filtered.slice(0, 10).map((s) => (
            <button
              key={s}
              type="button"
              className="w-full px-3 py-1.5 text-left text-sm hover:bg-accent hover:text-accent-foreground"
              onMouseDown={(e) => {
                e.preventDefault();
                addTag(s);
              }}
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
