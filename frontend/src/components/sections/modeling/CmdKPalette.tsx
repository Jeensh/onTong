"use client";

import { useEffect, useState } from "react";
import { useWorkbench } from "./store";
import { ontologyApi, type SearchHitDTO } from "@/lib/api/ontology";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { Network, Play, Search, Lightbulb } from "lucide-react";
import { prettyFqn } from "@/lib/modeling/fqn";

export function CmdKPalette() {
  const {
    cmdkOpen, toggleCmdK, cmdkInitialQuery,
    setSelectedAction, setSelectedTerm, setSelectedCodeType, setSelectedRule,
    setGraphMode, activeRepoId,
  } = useWorkbench();
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHitDTO[]>([]);
  // Did-you-mean — search 가 0-hit 일 때만 fetch (별도 endpoint 부하 최소화)
  const [suggestions, setSuggestions] = useState<SearchHitDTO[]>([]);
  // cmdk highlighted value — 검색 결과 도착 시 첫 hit 으로 강제. Enter 가 "그래프 모드"
  // 같은 명령 group 으로 빠지지 않도록 controlled.
  const [activeValue, setActiveValue] = useState<string>("");

  const itemValue = (h: SearchHitDTO, prefix: "hit" | "sug" = "hit") =>
    `${prefix}|${h.kind}|${h.fqn}`;

  // R2-3: 한국어 IME composition 중 Enter / 검색 결과 미도착 중 Enter 가 cmdk 의
  // 디폴트 첫 명령 ("그래프 모드") 으로 빠지는 버그. capture phase 에서 가로채서
  // composition 끝날 때까지 / 결과 도착할 때까지 swallow.
  const onInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== "Enter") return;
    // KeyboardEvent.isComposing — Chrome/Edge/Safari. nativeEvent fallback for typing.
    const composing =
      // @ts-expect-error — isComposing exists on KeyboardEvent in modern browsers
      (e.isComposing as boolean | undefined) ||
      (e.nativeEvent as unknown as { isComposing?: boolean }).isComposing ||
      // 229 = legacy keyCode for composition in progress
      e.keyCode === 229;
    if (composing) {
      e.stopPropagation();
      return;
    }
    // 검색 in-flight (query 있는데 hits/suggestions 둘 다 비어있음) — 결과 도착 전 Enter
    // 가 첫 명령으로 빠지지 않도록 보호. (debounce 150ms + fetch 200ms 동안 빈 활성값.)
    if (query.trim().length > 0 && hits.length === 0 && suggestions.length === 0) {
      e.stopPropagation();
      e.preventDefault();
    }
  };

  // 팔레트 열릴 때 좌측 트리 / 온톨로지 검색 입력 텍스트가 있으면 이어받음
  useEffect(() => {
    if (cmdkOpen) {
      setQuery(cmdkInitialQuery ?? "");
    } else {
      setQuery("");
    }
  }, [cmdkOpen, cmdkInitialQuery]);

  useEffect(() => {
    if (!cmdkOpen) return;
    if (!query.trim()) {
      setHits([]);
      setSuggestions([]);
      return;
    }
    let cancelled = false;
    setSuggestions([]);  // 새 쿼리 → 이전 suggestion 즉시 클리어
    const t = setTimeout(async () => {
      const d = await ontologyApi
        .search(query, { repo_id: activeRepoId, limit: 20 })
        .catch(() => [] as SearchHitDTO[]);
      if (cancelled) return;
      setHits(d);
      // 검색 결과 도착 → 첫 hit 으로 active value 강제. Enter 가 그쪽으로 가도록.
      if (d.length > 0) {
        setActiveValue(itemValue(d[0], "hit"));
      }
      // 0-hit 이면 fuzzy suggest 호출. 이미 결과 있으면 skip.
      if (d.length === 0 && query.trim().length >= 2) {
        const s = await ontologyApi
          .searchSuggest(query, { repo_id: activeRepoId, n: 5 })
          .catch(() => [] as SearchHitDTO[]);
        if (!cancelled) {
          setSuggestions(s);
          if (s.length > 0) setActiveValue(itemValue(s[0], "sug"));
        }
      }
    }, 150);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [cmdkOpen, query, activeRepoId]);

  const handlePick = (h: SearchHitDTO) => {
    if (h.kind === "action") setSelectedAction(h.fqn);
    else if (h.kind === "term") setSelectedTerm(h.fqn);
    else if (h.kind === "code_type") setSelectedCodeType(h.fqn);
    else if (h.kind === "rule") setSelectedRule(h.fqn);
    else if (h.kind === "code_method") {
      const parent = h.fqn.includes("(") ? h.fqn.slice(0, h.fqn.indexOf("(")).split(".").slice(0, -1).join(".") : h.fqn.split(".").slice(0, -1).join(".");
      if (parent) setSelectedCodeType(parent);
    }
    toggleCmdK(false);
  };

  return (
    <CommandDialog
      open={cmdkOpen}
      onOpenChange={(o) => toggleCmdK(o)}
      shouldFilter={false}
      value={activeValue}
      onValueChange={setActiveValue}
    >
      <CommandInput
        placeholder="검색 — 예: slabWidth · 너비 · design · DG001"
        value={query}
        onValueChange={setQuery}
        onKeyDownCapture={onInputKeyDown}
      />
      <CommandList>
        <CommandEmpty>
          {query.trim().length >= 2 && suggestions.length === 0
            ? "매칭 없음"
            : "검색어를 입력하세요"}
        </CommandEmpty>
        {hits.length > 0 && (
          <CommandGroup heading="검색 결과">
            {hits.map((h) => (
              <CommandItem
                key={`${h.kind}|${h.fqn}`}
                value={itemValue(h, "hit")}
                onSelect={() => handlePick(h)}
                className="flex items-center gap-2 min-w-0"
                title={h.fqn}
              >
                <Search className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                <span className="text-[11px] uppercase text-muted-foreground w-14 shrink-0">{h.kind}</span>
                <span className="font-mono text-xs truncate min-w-0 flex-1">
                  {prettyFqn(h.fqn, (h.kind === "code_type" ? "code_type" : h.kind === "action" ? "action" : h.kind === "term" ? "term" : "code_type") as never)}
                </span>
                <span className="ml-auto text-xs text-muted-foreground shrink-0 truncate max-w-[40%]">{h.label}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        )}
        {/* 0-hit 이고 fuzzy 추천이 있으면 surface — 페르소나 P3-F6 */}
        {hits.length === 0 && suggestions.length > 0 && (
          <CommandGroup heading="혹시 이거?">
            {suggestions.map((h) => (
              <CommandItem
                key={`sug|${h.kind}|${h.fqn}`}
                value={itemValue(h, "sug")}
                onSelect={() => handlePick(h)}
                className="flex items-center gap-2 min-w-0"
                title={h.fqn}
              >
                <Lightbulb className="w-3.5 h-3.5 text-amber-600/80 shrink-0" />
                <span className="text-[11px] uppercase text-muted-foreground w-14 shrink-0">{h.kind}</span>
                <span className="font-mono text-xs truncate min-w-0 flex-1">
                  {prettyFqn(h.fqn, (h.kind === "code_type" ? "code_type" : h.kind === "action" ? "action" : h.kind === "term" ? "term" : "code_type") as never)}
                </span>
                <span className="ml-auto text-xs text-muted-foreground shrink-0 truncate max-w-[40%]">{h.label}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        )}
        <CommandSeparator />
        <CommandGroup heading="명령">
          <CommandItem
            value="cmd|graph-mode"
            onSelect={() => {
              setGraphMode(true);
              toggleCmdK(false);
            }}
          >
            <Network className="w-3.5 h-3.5 mr-2" /> 그래프 모드
          </CommandItem>
          <CommandItem value="cmd|sim-start">
            <Play className="w-3.5 h-3.5 mr-2" /> 시뮬레이션 시작
            <span className="ml-auto text-[10.5px] text-muted-foreground">SIGNATURE_LOCKED+</span>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
