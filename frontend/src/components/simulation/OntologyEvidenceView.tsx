"use client";

import { useEffect, useState } from "react";
import { BookOpen, Search, Loader2 } from "lucide-react";
import { OntologyEvidencePanel } from "./OntologyEvidencePanel";
import { HelpPopover } from "./HelpPopover";

/** 자주 쓰는 action_fqn preset — 사용자가 빠르게 선택. */
const PRESET_ACTIONS = [
  {
    fqn: "action.scm.슬랩설계_실행",
    label: "🔝 슬랩 설계 실행 (workflow root)",
    desc: "21-step workflow 의 root — 모든 sub-action 을 BFS",
  },
  {
    fqn: "action.scm.std.match_customer_limit_for_order",
    label: "고객 한도 매칭 (match_customer_limit_for_order)",
    desc: "주문 ↔ 고객 신용한도 체크. verdict=sim_verified 핵심 시나리오",
  },
  {
    fqn: "action.scm.order.정합성_검증",
    label: "주문 정합성 검증 (validator)",
    desc: "DG001~005 — 재고/사이즈/포장단중/설계대기량/작업기한일",
  },
  {
    fqn: "action.scm.product.cumulative_productivity",
    label: "누적 실수율 (productivity)",
    desc: "활성 공정 실수율 곱 — anchor 풍부",
  },
  {
    fqn: "action.scm.thickness_실행",
    label: "Step 1 — 1차 두께 결정 (thickness)",
    desc: "CAST_SPEC 룩업 → Slab 두께",
  },
  {
    fqn: "action.scm.width_range_실행",
    label: "Step 2 — 1차 폭 범위 (width_range)",
    desc: "CAST ∩ HR_SPEC ∩ EDGING",
  },
  {
    fqn: "action.scm.length_range_실행",
    label: "Step 3 — 1차 길이 범위 (length_range)",
    desc: "CAST ∩ HR_SPEC",
  },
  {
    fqn: "action.scm.first_weight_실행",
    label: "Step 4 — 1차 단중",
    desc: "1차 단중 하/상한 결정",
  },
  {
    fqn: "action.scm.second_wgt_low_실행",
    label: "Step 5 — 2차 단중 하한",
    desc: "HR_MIN_WGT 2D 격자 룩업",
  },
  {
    fqn: "action.scm.second_wgt_high_실행",
    label: "Step 6 — 2차 단중 상한",
    desc: "HR_MAX_WGT 2D 격자 룩업",
  },
  {
    fqn: "action.scm.max_split_count_실행",
    label: "Step 7 — 최대 분할수",
    desc: "A-a 루프 시작점",
  },
  {
    fqn: "action.scm.split_range_실행",
    label: "Step 8 — 분할 범위",
    desc: "분할수 고려 단중 범위",
  },
  {
    fqn: "action.scm.slab.slab_count_실행",
    label: "★ Step 9 — Slab 매수",
    desc: "floor(설계대기량 ÷ 실수율 ÷ 단중)",
  },
  {
    fqn: "action.scm.slab.initial_slab_wgt_실행",
    label: "Step 10 — Slab 단중",
    desc: "설계대기량 만족 점검",
  },
  {
    fqn: "action.scm.final_width_range_실행",
    label: "Step 16 — 최종 폭 범위",
    desc: "최종 폭 하/상한",
  },
  {
    fqn: "action.scm.final_length_range_실행",
    label: "Step 17 — 최종 길이 범위",
    desc: "최종 길이 하/상한",
  },
  {
    fqn: "action.scm.target_width_실행",
    label: "Step 18 — 목표 폭",
    desc: "최종 목표 폭",
  },
  {
    fqn: "action.scm.target_length_실행",
    label: "Step 19 — 목표 길이",
    desc: "최종 목표 길이",
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
          🎯 자주 쓰는 action ({PRESET_ACTIONS.length}종) — 클릭해 즉시 evidence 보기.
          슬랩 설계 21-step workflow 의 각 sub-action 별로 다른 ontology trace 가 나옵니다.
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-2">
          {PRESET_ACTIONS.map((p) => (
            <button
              key={p.fqn}
              onClick={() => {
                setInputFqn(p.fqn);
                setActionFqn(p.fqn);
              }}
              title={`${p.fqn}\n${p.desc}`}
              className={`text-left rounded-md border px-2.5 py-2 transition-colors ${
                actionFqn === p.fqn
                  ? "border-primary bg-primary/10"
                  : "border-border hover:border-primary/40 hover:bg-muted/50"
              }`}
            >
              <div className="text-[11px] font-medium text-foreground leading-tight">{p.label}</div>
              <div className="text-[9px] text-muted-foreground mt-0.5 font-mono truncate">{p.fqn.replace("action.scm.", "")}</div>
              <div className="text-[10px] text-muted-foreground mt-1 leading-tight">{p.desc}</div>
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
