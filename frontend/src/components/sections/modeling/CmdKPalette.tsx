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
import { Network, Play, Search } from "lucide-react";

export function CmdKPalette() {
  const { cmdkOpen, toggleCmdK, setSelectedAction, setGraphMode, activeRepoId } = useWorkbench();
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHitDTO[]>([]);

  useEffect(() => {
    if (!cmdkOpen) return;
    if (!query.trim()) {
      setHits([]);
      return;
    }
    let cancelled = false;
    const t = setTimeout(() => {
      ontologyApi
        .search(query, { repo_id: activeRepoId, limit: 20 })
        .catch(() => [] as SearchHitDTO[])
        .then((d) => !cancelled && setHits(d));
    }, 150);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [cmdkOpen, query, activeRepoId]);

  return (
    <CommandDialog open={cmdkOpen} onOpenChange={(o) => toggleCmdK(o)}>
      <CommandInput
        placeholder="검색 또는 명령 (esc로 닫기)"
        value={query}
        onValueChange={setQuery}
      />
      <CommandList>
        <CommandEmpty>매칭 없음</CommandEmpty>
        {hits.length > 0 && (
          <CommandGroup heading="검색 결과">
            {hits.map((h) => (
              <CommandItem
                key={`${h.kind}|${h.fqn}`}
                onSelect={() => {
                  if (h.kind === "action") setSelectedAction(h.fqn);
                  toggleCmdK(false);
                }}
                className="flex items-center gap-2"
              >
                <Search className="w-3.5 h-3.5 text-muted-foreground" />
                <span className="text-[11px] uppercase text-muted-foreground w-14">{h.kind}</span>
                <span className="font-mono text-xs">{h.fqn}</span>
                <span className="ml-auto text-xs text-muted-foreground">{h.label}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        )}
        <CommandSeparator />
        <CommandGroup heading="명령">
          <CommandItem
            onSelect={() => {
              setGraphMode(true);
              toggleCmdK(false);
            }}
          >
            <Network className="w-3.5 h-3.5 mr-2" /> 그래프 모드
          </CommandItem>
          <CommandItem>
            <Play className="w-3.5 h-3.5 mr-2" /> 시뮬레이션 시작
            <span className="ml-auto text-[10.5px] text-muted-foreground">SIGNATURE_LOCKED+</span>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
