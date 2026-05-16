"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useWorkbench } from "./store";
import { cn } from "@/lib/utils";
import {
  ontologyApi,
  type ActionDTO,
  type AnchorBindingDTO,
  type BusinessRuleDTO,
  type CallSiteDTO,
  type CodeMethodDTO,
  type CodeTypeDTO,
} from "@/lib/api/ontology";
import { Loader2 } from "lucide-react";
import { HelpHint } from "./HelpHint";
import { JavaCode } from "./JavaCode";

const TABS = [
  { id: "code",     label: "📄 코드",       hint: null },
  { id: "callsite", label: "📞 호출지점",   hint: "call_site" },
  { id: "impact",   label: "🌊 영향",       hint: null },
  { id: "manual",   label: "📖 매뉴얼",     hint: null },
];

/**
 * 우측 사이드바 — 좌측 selection 에 따라 4 탭 content 가 바뀜.
 *
 * - Action 선택 시: 코드/호출지점/영향/매뉴얼 모두 의미 있음
 * - Term/CodeType/BR/Anchor 선택 시: 일부 탭만 활성, 나머지 "이 entity 에 적용 안 됨"
 * - 미선택: "선택 후 표시" 안내
 */
export function RightPanel() {
  const {
    rightWidth, setRightWidth, setMainMode,
    selectedActionFqn, selectedCodeTypeFqn, selectedTermFqn, selectedRuleFqn, selectedAnchorId,
  } = useWorkbench();
  const [activeTab, setActiveTab] = useState<string>("code");
  const dragRef = useRef<HTMLDivElement>(null);

  const selection = useMemo(() => {
    if (selectedActionFqn) return { kind: "action" as const, id: selectedActionFqn };
    if (selectedCodeTypeFqn) return { kind: "codeType" as const, id: selectedCodeTypeFqn };
    if (selectedTermFqn) return { kind: "term" as const, id: selectedTermFqn };
    if (selectedRuleFqn) return { kind: "rule" as const, id: selectedRuleFqn };
    if (selectedAnchorId) return { kind: "anchor" as const, id: selectedAnchorId };
    return null;
  }, [selectedActionFqn, selectedCodeTypeFqn, selectedTermFqn, selectedRuleFqn, selectedAnchorId]);

  useEffect(() => {
    const handle = dragRef.current;
    if (!handle) return;
    let dragging = false;
    const onDown = (e: MouseEvent) => {
      dragging = true;
      document.body.style.cursor = "col-resize";
      e.preventDefault();
    };
    const onMove = (e: MouseEvent) => {
      if (!dragging) return;
      setRightWidth(window.innerWidth - e.clientX);
    };
    const onUp = () => {
      dragging = false;
      document.body.style.cursor = "";
    };
    handle.addEventListener("mousedown", onDown);
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => {
      handle.removeEventListener("mousedown", onDown);
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
  }, [setRightWidth]);

  return (
    <aside
      className="bg-card border-l border-border flex flex-col overflow-hidden relative min-w-0"
      style={{ gridArea: "right", width: rightWidth }}
    >
      <div
        ref={dragRef}
        className="absolute left-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-primary z-10"
        title="드래그로 너비 조정"
      />
      {/* 탭 */}
      <div className="flex border-b border-border px-2 pt-1.5 shrink-0">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={cn(
              "rounded-t px-2 py-1 text-[11px] border-b-2 inline-flex items-center gap-0.5",
              activeTab === t.id
                ? "text-foreground border-primary"
                : "text-muted-foreground border-transparent hover:text-foreground",
            )}
          >
            {t.label}
            {t.hint && <HelpHint term={t.hint} inline />}
          </button>
        ))}
      </div>

      {/* selection breadcrumb */}
      <div className="px-2.5 py-1 border-b border-border bg-muted/40 flex gap-1.5 items-center text-[10.5px] shrink-0">
        {selection ? (
          <span className="truncate min-w-0 flex-1">
            <span className="text-muted-foreground">선택:</span>{" "}
            <span className="font-mono text-foreground">{selection.id.split(".").pop() ?? selection.id}</span>{" "}
            <span className="text-muted-foreground">({selection.kind})</span>
          </span>
        ) : (
          <span className="text-muted-foreground flex-1">선택 없음</span>
        )}
        {selectedActionFqn && (
          <button
            onClick={() => setMainMode("split")}
            className="text-[10.5px] px-2 py-0.5 rounded border border-primary text-primary hover:bg-primary/10 shrink-0"
            title="↕ Split mode 로"
          >
            ↕ Split
          </button>
        )}
      </div>

      {/* 본문 */}
      <div className="overflow-y-auto flex-1 p-2.5 text-xs min-w-0">
        {!selection && (
          <p className="text-muted-foreground p-3">
            좌측 트리에서 entity 선택 시 우측 표시.
          </p>
        )}
        {selection && activeTab === "code" && <TabCode selection={selection} />}
        {selection && activeTab === "callsite" && <TabCallSite selection={selection} />}
        {selection && activeTab === "impact" && <TabImpact selection={selection} />}
        {selection && activeTab === "manual" && <TabManual selection={selection} />}
      </div>
    </aside>
  );
}

type Selection = {
  kind: "action" | "codeType" | "term" | "rule" | "anchor";
  id: string;
};

// ─────────────────────────────────────────────────────────────────────────
// 탭 1 — 코드 본체
// ─────────────────────────────────────────────────────────────────────────
function TabCode({ selection }: { selection: Selection }) {
  const [content, setContent] = useState<{ method?: CodeMethodDTO; codeType?: CodeTypeDTO } | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setContent(null);
    (async () => {
      try {
        if (selection.kind === "action") {
          const a = await ontologyApi.getAction(selection.id);
          if (!a) return;
          const r = a.realizations.find(x => x.scope === "primary") ?? a.realizations[0];
          if (!r) return;
          const parent = parentTypeFqnOfMethod(r.code_method_fqn);
          if (!parent) return;
          const ct = await ontologyApi.getCodeType(parent);
          const m = ct?.methods.find(mm => mm.fqn === r.code_method_fqn);
          if (!cancelled) setContent({ method: m, codeType: ct ?? undefined });
        } else if (selection.kind === "codeType") {
          const ct = await ontologyApi.getCodeType(selection.id);
          if (!cancelled) setContent({ codeType: ct ?? undefined });
        } else if (selection.kind === "anchor") {
          const all = await ontologyApi.listAnchorBindings({ repo_id: "slab-design-real" });
          const a = all.find(x => x.id === selection.id);
          if (!a) return;
          const parent = parentTypeFqnOfMethod(a.code_method_fqn);
          if (!parent) return;
          const ct = await ontologyApi.getCodeType(parent);
          const m = ct?.methods.find(mm => mm.fqn === a.code_method_fqn);
          if (!cancelled) setContent({ method: m, codeType: ct ?? undefined });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [selection.kind, selection.id]);

  if (loading) return <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />;

  if (selection.kind === "term" || selection.kind === "rule") {
    return (
      <p className="text-muted-foreground p-2">
        {selection.kind === "term" ? "Term" : "BusinessRule"} 은 코드 method 와 직접 매핑 안 됨.
        대신 <strong className="text-foreground">호출지점</strong> 또는 <strong className="text-foreground">영향</strong> 탭 참고.
      </p>
    );
  }

  if (!content) return <p className="text-muted-foreground p-2">코드 정보 없음.</p>;

  if (content.method?.body_text) {
    const m = content.method;
    return (
      <div>
        <div className="text-[10.5px] text-muted-foreground mb-1 break-all">
          {m.parent_type_fqn}
        </div>
        <div className="text-[11px] text-foreground mb-1.5 font-semibold break-all">
          {m.name}({m.params.map(p => p.type).join(", ")}) → {m.return_type}
        </div>
        <div className="text-[10px] text-muted-foreground mb-2">
          line {m.line_start}–{m.line_end} · role: {m.role}
        </div>
        <div className="bg-muted border border-border rounded text-[11px] overflow-x-auto">
          <JavaCode source={m.body_text ?? ""} startLine={m.line_start ?? 1} />
        </div>
      </div>
    );
  }

  if (content.codeType) {
    const ct = content.codeType;
    return (
      <div>
        <div className="text-[10.5px] text-muted-foreground break-all mb-1">{ct.fqn}</div>
        <div className="text-[11px] text-foreground mb-1.5 font-semibold">{ct.simple_name}</div>
        <div className="text-[10px] text-muted-foreground mb-2">
          {ct.kind} · role {ct.role} · {ct.fields.length} field · {ct.methods.length} method
        </div>
        <div className="text-[10px] text-muted-foreground mt-2 break-all">{ct.source_file}</div>
        <p className="text-[11px] text-muted-foreground mt-2">
          (전체 detail 은 가운데 패널 참고. 우측은 요약.)
        </p>
      </div>
    );
  }

  return <p className="text-muted-foreground p-2">코드 본체 없음.</p>;
}

// ─────────────────────────────────────────────────────────────────────────
// 탭 2 — 호출지점 (이 method/action 을 호출하는 caller, 또는 이 method 가 호출하는 callee)
// ─────────────────────────────────────────────────────────────────────────
function TabCallSite({ selection }: { selection: Selection }) {
  const [callSites, setCallSites] = useState<CallSiteDTO[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setCallSites([]);
    setErr(null);
    (async () => {
      try {
        let methodFqn: string | null = null;
        if (selection.kind === "action") {
          const a = await ontologyApi.getAction(selection.id);
          const r = a?.realizations.find(x => x.scope === "primary") ?? a?.realizations[0];
          methodFqn = r?.code_method_fqn ?? null;
        }
        // codeType 의 경우 callees 가 너무 많으니 skip
        if (methodFqn) {
          const cs = await ontologyApi.getCallSites(methodFqn);
          if (!cancelled) setCallSites(cs);
        }
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [selection.kind, selection.id]);

  if (loading) return <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />;
  if (err) {
    return (
      <div className="p-2 text-[11px]">
        <div className="text-rose-700 mb-1">호출지점 로드 실패</div>
        <div className="text-muted-foreground break-all">{err}</div>
        <div className="text-muted-foreground mt-2">
          backend 가 재시작 직후라면 잠시 후 새로고침 해보세요.
        </div>
      </div>
    );
  }

  if (selection.kind !== "action") {
    return (
      <p className="text-muted-foreground p-2">
        호출지점은 Action 또는 CodeMethod 선택 시만 표시. 현재 {selection.kind}.
      </p>
    );
  }
  if (callSites.length === 0) {
    return <p className="text-muted-foreground p-2">이 Action 의 method 가 호출하는 다른 method 없음 (또는 분석 미수행).</p>;
  }

  return (
    <div className="space-y-1">
      <div className="text-[10.5px] text-muted-foreground mb-1">
        이 method 가 호출하는 곳 · {callSites.length}건 <HelpHint term="call_site" inline />
      </div>
      {callSites.slice(0, 50).map((cs) => (
        <div key={cs.id} className="bg-muted px-2 py-1 rounded text-[11px]">
          <div className="flex items-center gap-1.5">
            <span className="font-mono text-foreground truncate flex-1 min-w-0 break-all">
              {cs.callee_simple_name}
            </span>
            {cs.line && <span className="font-mono text-[9.5px] text-muted-foreground shrink-0">L{cs.line}</span>}
          </div>
          <div className="text-[10px] text-muted-foreground mt-0.5 break-all">
            on {cs.callee_receiver_static_type} · {cs.analysis_source}
            {cs.needs_user_confirm && <span className="ml-1 text-amber-700">(모호)</span>}
          </div>
          {cs.user_confirmed_type && (
            <div className="text-[10px] text-emerald-700 mt-0.5">
              ✓ confirmed: {cs.user_confirmed_type.split(".").pop()}
            </div>
          )}
        </div>
      ))}
      {callSites.length > 50 && (
        <p className="text-[10px] text-muted-foreground">… {callSites.length - 50} 더</p>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// 탭 3 — 영향 (이 entity 와 연결된 다른 ontology 노드들)
// ─────────────────────────────────────────────────────────────────────────
function TabImpact({ selection }: { selection: Selection }) {
  const { activeRepoId } = useWorkbench();
  const [data, setData] = useState<{
    actions?: ActionDTO[];
    rules?: BusinessRuleDTO[];
    anchors?: AnchorBindingDTO[];
    relatedTerms?: string[];
  } | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setData(null);
    (async () => {
      try {
        if (selection.kind === "action") {
          // sub_actions / referenced anchors / enforced BRs
          const a = await ontologyApi.getAction(selection.id);
          if (!a) return;
          const ans = await ontologyApi.getAnchorBindingsForAction(selection.id).catch(() => []);
          const allRules = await ontologyApi.listBusinessRules({ repo_id: activeRepoId }).catch(() => []);
          const r = a.realizations.find(x => x.scope === "primary") ?? a.realizations[0];
          const enforced = r ? allRules.filter(rr => rr.enforced_by.includes(r.code_method_fqn)) : [];
          if (!cancelled) setData({ rules: enforced, anchors: ans });
        } else if (selection.kind === "term") {
          // 이 term 을 사용하는 actions (declared_on 또는 params)
          const actions = await ontologyApi.listActions({ repo_id: activeRepoId, declared_on_term: selection.id }).catch(() => []);
          // 이 term 을 ref 하는 BR
          const allRules = await ontologyApi.listBusinessRules({ repo_id: activeRepoId }).catch(() => []);
          const refRules = allRules.filter(r => r.terms_ref.includes(selection.id));
          if (!cancelled) setData({ actions, rules: refRules });
        } else if (selection.kind === "rule") {
          const allRules = await ontologyApi.listBusinessRules({ repo_id: activeRepoId }).catch(() => []);
          const r = allRules.find(rr => rr.fqn === selection.id);
          if (!cancelled) setData({ relatedTerms: r?.terms_ref ?? [] });
        } else if (selection.kind === "anchor") {
          const ans = await ontologyApi.listAnchorBindings({ repo_id: activeRepoId });
          const a = ans.find(x => x.id === selection.id);
          if (!a) return;
          const action = await ontologyApi.getAction(a.target_action_fqn).catch(() => null);
          if (!cancelled) setData({ actions: action ? [action] : [] });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [selection.kind, selection.id, activeRepoId]);

  const { setSelectedAction, setSelectedTerm, setSelectedRule } = useWorkbench();

  if (loading) return <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />;
  if (!data) return <p className="text-muted-foreground p-2">데이터 없음.</p>;

  return (
    <div className="space-y-3">
      {data.actions && data.actions.length > 0 && (
        <div>
          <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground font-semibold mb-1">
            연결 Actions · {data.actions.length}
          </div>
          {data.actions.map((a) => (
            <button
              key={a.fqn}
              onClick={() => setSelectedAction(a.fqn)}
              className="w-full text-left bg-muted hover:bg-orange-50 px-2 py-1 rounded text-[11px] my-0.5 block"
            >
              <div className="flex items-center gap-1">
                <span className="font-mono text-foreground truncate flex-1 break-all">{a.fqn}</span>
              </div>
              <div className="text-[10px] text-muted-foreground">{a.label} · {a.kind}</div>
            </button>
          ))}
        </div>
      )}
      {data.rules && data.rules.length > 0 && (
        <div>
          <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground font-semibold mb-1">
            연결 BR · {data.rules.length}
          </div>
          {data.rules.map((r) => (
            <button
              key={r.fqn}
              onClick={() => setSelectedRule(r.fqn)}
              className="w-full text-left bg-muted hover:bg-rose-50 px-2 py-1 rounded text-[11px] my-0.5 block"
            >
              <div className="flex items-center gap-1.5">
                <span className={cn(
                  "w-1.5 h-1.5 rounded-sm shrink-0",
                  r.severity === "hard" ? "bg-rose-500" : "bg-amber-500"
                )} />
                <span className="font-mono text-foreground truncate flex-1 break-all">{r.fqn}</span>
              </div>
              <div className="text-[10px] text-muted-foreground line-clamp-1">{r.statement}</div>
            </button>
          ))}
        </div>
      )}
      {data.anchors && data.anchors.length > 0 && (
        <div>
          <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground font-semibold mb-1">
            연결 Anchor · {data.anchors.length}
          </div>
          {data.anchors.map((a) => (
            <div key={a.id} className="bg-muted px-2 py-1 rounded text-[11px] my-0.5">
              <div className="flex items-center gap-1.5">
                <span className="font-mono text-[9.5px] text-sky-700">L{a.line ?? "?"}</span>
                <span className="font-mono truncate flex-1 break-all">{a.anchor_locator}</span>
              </div>
              <div className="text-[10px] text-muted-foreground break-all">→ {a.target_slot}</div>
            </div>
          ))}
        </div>
      )}
      {data.relatedTerms && data.relatedTerms.length > 0 && (
        <div>
          <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground font-semibold mb-1">
            참조 Terms · {data.relatedTerms.length}
          </div>
          {data.relatedTerms.map((t) => (
            <button
              key={t}
              onClick={() => setSelectedTerm(t)}
              className="w-full text-left bg-muted hover:bg-violet-50 px-2 py-1 rounded text-[11px] my-0.5 font-mono break-all block"
            >
              {t}
            </button>
          ))}
        </div>
      )}
      {!data.actions?.length && !data.rules?.length && !data.anchors?.length && !data.relatedTerms?.length && (
        <p className="text-muted-foreground text-[11px]">연결된 ontology 노드 없음.</p>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// 탭 4 — 매뉴얼 (Phase E — 위키 인덱스 연계)
// ─────────────────────────────────────────────────────────────────────────
function TabManual({ selection: _selection }: { selection: Selection }) {
  return (
    <div className="text-muted-foreground space-y-2 p-1">
      <p>📖 매뉴얼 fragment 연동 — Phase E.</p>
      <p className="text-[10.5px]">
        Section 1 (wiki) 의 매뉴얼 문서에서 본 entity 의 label / fqn alias 매칭하는 fragment 추출 예정.
        예: BusinessRule statement 와 wiki 의 운영 매뉴얼 절을 cross-reference.
      </p>
      <p className="text-[10.5px]">
        현 phase 에서는 미구현. 좌측 트리의 entity 와 wiki 검색을 별도로 활용.
      </p>
    </div>
  );
}

/** "com.foo.Bar.method(Args)" → "com.foo.Bar". */
function parentTypeFqnOfMethod(methodFqn: string): string | null {
  const parenIdx = methodFqn.indexOf("(");
  const beforeParen = parenIdx >= 0 ? methodFqn.slice(0, parenIdx) : methodFqn;
  const lastDot = beforeParen.lastIndexOf(".");
  if (lastDot < 0) return null;
  return beforeParen.slice(0, lastDot);
}
