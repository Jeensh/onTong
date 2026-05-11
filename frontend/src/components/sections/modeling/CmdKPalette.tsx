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
import { HelpHint } from "./HelpHint";

// kind → glossary key. Keep in sync with KindBadge in ModuleTree.
const KIND_GLOSSARY: Record<SearchHitDTO["kind"], string> = {
  code_type: "code_type",
  code_method: "code_method",
  term: "term",
  action: "action",
  rule: "business_rule",
};

export function CmdKPalette() {
  const {
    cmdkOpen, toggleCmdK,
    setSelectedAction, setSelectedTerm, setSelectedCodeType, setSelectedRule,
    openPeek,
    setGraphMode, activeRepoId,
  } = useWorkbench();
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
            {(() => {
              // Track each kind's first row so HelpHint shows once per kind —
              // avoids cluttering 20-row result lists while still teaching the
              // 5-kind taxonomy to first-time users.
              const seenKinds = new Set<SearchHitDTO["kind"]>();
              return hits.map((h) => {
                const isFirstOfKind = !seenKinds.has(h.kind);
                seenKinds.add(h.kind);
                return (
                  <CommandItem
                    key={`${h.kind}|${h.fqn}`}
                    onSelect={() => {
                      // Mirror FqnLink semantics so the palette matches every other
                      // search-result surface in the app.
                      if (h.kind === "action") setSelectedAction(h.fqn);
                      else if (h.kind === "term") setSelectedTerm(h.fqn);
                      else if (h.kind === "code_type") setSelectedCodeType(h.fqn);
                      else if (h.kind === "rule") setSelectedRule(h.fqn);
                      else if (h.kind === "code_method") {
                        // method has no Detail of its own — open Code Peek modal,
                        // keeping the current Detail selection intact.
                        openPeek({ kind: "code_method", fqn: h.fqn, repoId: activeRepoId });
                      }
                      toggleCmdK(false);
                    }}
                    className="flex items-center gap-2"
                  >
                    <Search className="w-3.5 h-3.5 text-muted-foreground" />
                    <span className="text-[11px] uppercase text-muted-foreground w-14 inline-flex items-center">
                      {h.kind}
                      {isFirstOfKind && <HelpHint term={KIND_GLOSSARY[h.kind]} inline />}
                    </span>
                    <span className="font-mono text-xs">{h.fqn}</span>
                    <span className="ml-auto text-xs text-muted-foreground">{h.label}</span>
                  </CommandItem>
                );
              });
            })()}
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
            <HelpHint term="mapping" inline />
          </CommandItem>
          <CommandItem>
            <Play className="w-3.5 h-3.5 mr-2" /> 시뮬레이션 시작
            <span className="ml-auto text-[10.5px] text-muted-foreground inline-flex items-center">
              SIGNATURE_LOCKED+
              <HelpHint term="signature_locked" inline />
            </span>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
