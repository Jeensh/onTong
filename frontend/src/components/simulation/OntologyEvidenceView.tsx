"use client";

import { useEffect, useState } from "react";
import { BookOpen, Search, Loader2 } from "lucide-react";
import { OntologyEvidencePanel } from "./OntologyEvidencePanel";
import { HelpPopover } from "./HelpPopover";

/** 자주 쓰는 action_fqn preset — 사용자가 빠르게 선택. */
const PRESET_ACTIONS = [
  {
    fqn: "action.scm.std.match_customer_limit_for_order",
    label: "고객 한도 매칭 (match_customer_limit_for_order)",
    desc: "주문에 대한 고객 신용한도 체크 — verdict=sim_verified 시나리오의 root action",
  },
  {
    fqn: "action.scm.슬랩설계_실행",
    label: "슬랩 설계 실행 (21-step workflow)",
    desc: "주문 → 슬랩 사이즈 도출 21단계 — Section 3 의 핵심 시뮬 대상",
  },
];

interface ListAction {
  fqn: string;
  label?: string;
  kind?: string;
}

export function OntologyEvidenceView() {
  const [actionFqn, setActionFqn] = useState<string>(PRESET_ACTIONS[0].fqn);
  const [inputFqn, setInputFqn] = useState<string>(PRESET_ACTIONS[0].fqn);
  const [actions, setActions] = useState<ListAction[]>([]);
  const [filterText, setFilterText] = useState<string>("");
  const [listLoading, setListLoading] = useState(false);
  const [listErr, setListErr] = useState<string | null>(null);

  useEffect(() => {
    let aborted = false;
    setListLoading(true);
    fetch("/api/ontology/actions")
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => {
        if (aborted) return;
        const arr = Array.isArray(d) ? d : (d.actions ?? d.items ?? []);
        setActions(arr);
      })
      .catch((e) => {
        if (!aborted) setListErr(String(e));
      })
      .finally(() => {
        if (!aborted) setListLoading(false);
      });
    return () => {
      aborted = true;
    };
  }, []);

  const filtered = filterText
    ? actions
        .filter(
          (a) =>
            a.fqn.toLowerCase().includes(filterText.toLowerCase()) ||
            (a.label ?? "").toLowerCase().includes(filterText.toLowerCase()),
        )
        .slice(0, 20)
    : [];

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-2">
        <BookOpen size={20} className="text-primary mt-0.5" />
        <div>
          <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
            온톨로지 근거 (Section 2 ontology trace)
            <HelpPopover
              title="온톨로지 근거 보기"
              body={
                <div className="space-y-2 text-xs">
                  <p>
                    Section 3 시뮬레이션의 모든 결과는 Section 2 의 온톨로지 모델링
                    (Action / Realization / BusinessRule / AnchorBinding) 에서 derive 됩니다.
                  </p>
                  <p>
                    이 화면은 특정 action 의 4 evidence kind 를 ontology 에서 직접 조회해
                    "이 기능이 ontology 의 어디에서 나왔는지" 를 한눈에 보여줍니다.
                  </p>
                  <p className="text-muted-foreground">
                    facade: <code>backend.modeling.api.ontology_query.OntologyQueryClientImpl</code>
                  </p>
                </div>
              }
            />
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            action_fqn 선택 → 4 evidence kind (Action / Realization / BR / AnchorBinding) 의
            실 ontology 데이터를 trace
          </p>
        </div>
      </div>

      {/* preset action chips */}
      <div className="rounded-lg border border-border bg-card p-4 space-y-3">
        <div className="text-xs font-medium text-muted-foreground">
          🎯 자주 쓰는 action — 클릭해 즉시 evidence 보기
        </div>
        <div className="flex flex-wrap gap-2">
          {PRESET_ACTIONS.map((p) => (
            <button
              key={p.fqn}
              onClick={() => {
                setInputFqn(p.fqn);
                setActionFqn(p.fqn);
              }}
              title={p.desc}
              className={`text-left rounded-lg border px-3 py-2 transition-colors ${
                actionFqn === p.fqn
                  ? "border-primary bg-primary/10"
                  : "border-border hover:border-primary/40 hover:bg-muted/50"
              }`}
            >
              <div className="text-[12px] font-medium text-foreground">{p.label}</div>
              <div className="text-[10px] text-muted-foreground mt-0.5 font-mono">{p.fqn}</div>
              <div className="text-[10px] text-muted-foreground mt-1">{p.desc}</div>
            </button>
          ))}
        </div>

        {/* free input + list search */}
        <div className="border-t border-border/60 pt-3 space-y-2">
          <div className="text-xs font-medium text-muted-foreground">
            🔎 또는 ontology 에 등록된 action_fqn 직접 입력 / 검색{" "}
            {listLoading && (
              <Loader2 size={12} className="inline animate-spin ml-1" />
            )}
            {!listLoading && actions.length > 0 && (
              <span className="text-muted-foreground/60">
                (총 {actions.length} action 로딩됨)
              </span>
            )}
            {listErr && <span className="text-red-500">{listErr}</span>}
          </div>
          <div className="flex gap-2 items-stretch">
            <div className="flex-1 relative">
              <Search
                size={14}
                className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground"
              />
              <input
                type="text"
                value={inputFqn}
                onChange={(e) => {
                  setInputFqn(e.target.value);
                  setFilterText(e.target.value);
                }}
                placeholder="action.scm.std.match_customer_limit_for_order"
                className="w-full pl-7 pr-2 py-1.5 text-[12px] font-mono rounded border border-border bg-background"
              />
              {filtered.length > 0 && (
                <div className="absolute z-10 mt-1 w-full max-h-60 overflow-auto rounded border border-border bg-popover shadow-lg">
                  {filtered.map((a) => (
                    <button
                      key={a.fqn}
                      onClick={() => {
                        setInputFqn(a.fqn);
                        setActionFqn(a.fqn);
                        setFilterText("");
                      }}
                      className="w-full text-left px-3 py-1.5 hover:bg-muted text-[11px]"
                    >
                      <div className="font-mono text-[11px] text-foreground truncate">
                        {a.fqn}
                      </div>
                      {a.label && (
                        <div className="text-[10px] text-muted-foreground truncate">
                          {a.label}
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button
              onClick={() => setActionFqn(inputFqn)}
              className="px-3 py-1.5 rounded border border-primary bg-primary text-primary-foreground text-[12px] hover:bg-primary/90"
            >
              조회
            </button>
          </div>
        </div>
      </div>

      {/* evidence panel */}
      <OntologyEvidencePanel actionFqn={actionFqn} variant="card" autoOpen />

      {/* 안내 */}
      <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-[11px] text-amber-800 dark:text-amber-300">
        💡 spec 03 run (POST /api/simulation/runs) 의 결과를 추적하려면 <b>실행 이력</b>{" "}
        화면에서 run 의 상세 토글을 눌러 "📚 온톨로지 근거 보기" 를 선택하세요. 거기서는
        실제 dispatch / BR / anchor 의 trace 가 함께 노출됩니다.
      </div>
    </div>
  );
}
