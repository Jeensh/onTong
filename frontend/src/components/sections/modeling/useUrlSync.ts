"use client";

/**
 * URL ↔ Workbench store 양방향 sync (R4-T2.3, 안건 5 B).
 *
 * - Saved Perspective: ?p=42 → fetch + apply spec
 * - Ad-hoc state: ?repo=... &mode=... &focus=... &target=... &n_max=... → 직접 store
 * - State 변화 감지 → URL replace (debounced, 히스토리 push 안 함)
 *
 * 정책:
 * - mount 시 URL → store (initial sync). 그 후 store → URL.
 * - Saved + override (?p=42&focus=...) — saved 적용 후 override 부분만 store 에 추가 set.
 * - graph mode 활성 시에만 graph 파라미터 sync (다른 mode 영향 X).
 */
import { useEffect, useRef } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { ontologyApi } from "@/lib/api/ontology";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import type { SectionId } from "@/types";
import { useWorkbench } from "./store";

export function useUrlSync() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const initializedRef = useRef(false);
  const lastUrlRef = useRef<string>("");

  // store getters
  const activeSection  = useWorkspaceStore((s) => s.activeSection);
  const setActiveSection = useWorkspaceStore((s) => s.setActiveSection);
  const repoId         = useWorkbench((s) => s.activeRepoId);
  const graphMode      = useWorkbench((s) => s.graphMode);
  const graphFocus     = useWorkbench((s) => s.graphFocus);
  const graphTarget    = useWorkbench((s) => s.graphTarget);
  const graphNMax      = useWorkbench((s) => s.graphNMax);
  const graphActive    = useWorkbench((s) => s.graphModeActive);
  const perspectiveId  = useWorkbench((s) => s.activePerspectiveId);
  // F0-2: 단일 entity selection (graph 와 무관 — incident share URL)
  const selectedActionFqn   = useWorkbench((s) => s.selectedActionFqn);
  const selectedCodeTypeFqn = useWorkbench((s) => s.selectedCodeTypeFqn);
  const selectedTermFqn     = useWorkbench((s) => s.selectedTermFqn);
  const selectedRuleFqn     = useWorkbench((s) => s.selectedRuleFqn);
  const selectedAnchorId    = useWorkbench((s) => s.selectedAnchorId);
  const selectOnly          = useWorkbench((s) => s.selectOnly);
  // 새 IA
  const graphTopMode     = useWorkbench((s) => s.graphTopMode);
  const coverageLenses   = useWorkbench((s) => s.coverageLenses);
  const impactFocusFqn   = useWorkbench((s) => s.impactFocusFqn);
  const impactFocusKind  = useWorkbench((s) => s.impactFocusKind);
  const impactHops       = useWorkbench((s) => s.impactHops);
  const impactDirection  = useWorkbench((s) => s.impactDirection);
  // setters
  const setRepoId             = useWorkbench((s) => s.setRepoId);
  const setGraphMode          = useWorkbench((s) => s.setGraphMode);
  const applyGraphState       = useWorkbench((s) => s.applyGraphState);
  const setActivePerspectiveId = useWorkbench((s) => s.setActivePerspectiveId);
  const setGraphTopMode       = useWorkbench((s) => s.setGraphTopMode);
  const setCoverageLenses     = useWorkbench((s) => s.setCoverageLenses);
  const jumpToImpact          = useWorkbench((s) => s.jumpToImpact);
  const setImpactHops         = useWorkbench((s) => s.setImpactHops);
  const setImpactDirection    = useWorkbench((s) => s.setImpactDirection);

  // ── 1. URL → store (initial mount, also on URL nav change) ─────────────────
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    const section = searchParams.get("section");
    const repo = searchParams.get("repo");
    const view = searchParams.get("view");
    const pid = searchParams.get("p");
    const mode = searchParams.get("mode");
    const focus = searchParams.get("focus");
    const target = searchParams.get("target");
    const nMaxStr = searchParams.get("n_max");
    // 새 IA 파라미터
    const gtm = searchParams.get("graph_mode");          // coverage / impact / explore
    if (gtm === "coverage" || gtm === "impact" || gtm === "explore") setGraphTopMode(gtm);
    const lensesStr = searchParams.get("lenses");        // "draft,orphan,recent"
    if (lensesStr !== null) {
      const valid = ["draft", "orphan", "recent"] as const;
      const picked = lensesStr.split(",").filter((x): x is typeof valid[number] => (valid as readonly string[]).includes(x));
      if (picked.length) setCoverageLenses(picked);
    }
    const impactFocusParam = searchParams.get("impact_focus");
    const impactKindParam = searchParams.get("impact_kind");
    if (impactFocusParam && (impactKindParam === "action" || impactKindParam === "term" || impactKindParam === "code_type" || impactKindParam === "code_method")) {
      jumpToImpact(impactFocusParam, impactKindParam);
    }
    const hopsStr = searchParams.get("hops");
    if (hopsStr) {
      const n = Number(hopsStr);
      if (Number.isFinite(n)) setImpactHops(n);
    }
    const dirStr = searchParams.get("dir");
    if (dirStr === "forward" || dirStr === "backward" || dirStr === "both") setImpactDirection(dirStr);

    // 섹션 (workspace) — graph view 가 있으면 modeling 자동 진입
    if (section === "wiki" || section === "modeling" || section === "simulation") {
      if (section !== activeSection) setActiveSection(section as SectionId);
    } else if (view === "graph" && activeSection !== "modeling") {
      setActiveSection("modeling" as SectionId);
    }
    if (repo && repo !== repoId) setRepoId(repo);
    if (view === "graph") setGraphMode(true);

    // F0-2: deep-link selection — ?sel=<fqn>&sel_kind=<kind>.
    // Graph focus (?focus=) 와 분리된 channel — 인시던트 URL share 시 entity 1개 선택만
    // 필요한 케이스. graph mode 가 아닐 때 단독 사용.
    // R3-2: codeMethod kind 도 수용 — 부모 codeType 으로 fallback 매핑 (selectOnly 는
    // codeType 만 지원). 이전엔 silent strip 이라 PR/티켓 URL share 가 method 단위에서
    // 깨졌음 (페르소나 B).
    const sel = searchParams.get("sel");
    const selKindRaw = searchParams.get("sel_kind");
    const validSelKinds = ["action", "codeType", "term", "rule", "anchor"] as const;
    type SelKind = typeof validSelKinds[number];
    if (sel && selKindRaw) {
      let resolvedKind: SelKind | null = null;
      let resolvedSel: string = sel;
      if ((validSelKinds as readonly string[]).includes(selKindRaw)) {
        resolvedKind = selKindRaw as SelKind;
      } else if (selKindRaw === "codeMethod" || selKindRaw === "code_method") {
        // method fqn 에서 parent type fqn 추출 — "com.foo.Bar.method(...)" → "com.foo.Bar"
        const parenIdx = sel.indexOf("(");
        const beforeParen = parenIdx >= 0 ? sel.slice(0, parenIdx) : sel;
        const lastDot = beforeParen.lastIndexOf(".");
        if (lastDot > 0) {
          resolvedSel = beforeParen.slice(0, lastDot);
          resolvedKind = "codeType";
        }
      }
      if (resolvedKind) {
        if (activeSection !== "modeling") setActiveSection("modeling" as SectionId);
        selectOnly(resolvedKind, resolvedSel);
      }
    }

    // Saved perspective fetch
    if (pid) {
      const id = Number(pid);
      if (Number.isFinite(id)) {
        const targetRepo = repo ?? repoId;
        ontologyApi.getPerspective(targetRepo, id)
          .then((p) => {
            applyGraphState({
              mode: (p.spec.mode as "neighborhood" | "path" | "cluster"),
              focus: p.spec.focus_fqn ?? null,
              target: p.spec.target_fqn ?? null,
              nMax: p.spec.n_max,
            });
            setActivePerspectiveId(p.id ?? null);
            // Override params (Saved + override)
            const patch: {
              mode?: "neighborhood" | "path" | "cluster";
              focus?: string | null;
              target?: string | null;
              nMax?: number;
            } = {};
            if (mode === "neighborhood" || mode === "path" || mode === "cluster") patch.mode = mode;
            if (focus !== null) patch.focus = focus || null;
            if (target !== null) patch.target = target || null;
            if (nMaxStr) patch.nMax = Math.max(10, Math.min(600, Number(nMaxStr) || 60));
            if (Object.keys(patch).length > 0) applyGraphState(patch);
          })
          .catch(() => {
            // perspective 못 찾으면 ad-hoc params 만이라도 적용
            applyAdHoc(mode, focus, target, nMaxStr);
          });
        return;
      }
    }

    // Ad-hoc only
    applyAdHoc(mode, focus, target, nMaxStr);

    function applyAdHoc(
      mode: string | null,
      focus: string | null,
      target: string | null,
      nMaxStr: string | null,
    ) {
      const patch: {
        mode?: "neighborhood" | "path" | "cluster";
        focus?: string | null;
        target?: string | null;
        nMax?: number;
      } = {};
      if (mode === "neighborhood" || mode === "path" || mode === "cluster") patch.mode = mode;
      if (focus !== null) patch.focus = focus || null;
      if (target !== null) patch.target = target || null;
      if (nMaxStr) patch.nMax = Math.max(10, Math.min(600, Number(nMaxStr) || 60));
      if (Object.keys(patch).length > 0) applyGraphState(patch);
    }
  }, [
    searchParams, activeSection, setActiveSection,
    repoId, setRepoId, setGraphMode, applyGraphState,
    setActivePerspectiveId,
  ]);

  // ── 2. store → URL (mutation, debounced) ───────────────────────────────────
  useEffect(() => {
    if (!initializedRef.current) return;
    const handle = setTimeout(() => {
      const params = new URLSearchParams();
      // 항상 section (modeling 일 때만 명시 — wiki 는 default 라 생략)
      if (activeSection !== "wiki") params.set("section", activeSection);
      if (repoId) params.set("repo", repoId);
      // F0-2: deep-link selection writeback. graph 가 활성 아닐 때만 — graph 자체 focus 와 분리.
      if (activeSection === "modeling" && !graphActive) {
        let sel: string | null = null;
        let selKind: string | null = null;
        if (selectedActionFqn)         { sel = selectedActionFqn;   selKind = "action"; }
        else if (selectedCodeTypeFqn)  { sel = selectedCodeTypeFqn; selKind = "codeType"; }
        else if (selectedTermFqn)      { sel = selectedTermFqn;     selKind = "term"; }
        else if (selectedRuleFqn)      { sel = selectedRuleFqn;     selKind = "rule"; }
        else if (selectedAnchorId)     { sel = selectedAnchorId;    selKind = "anchor"; }
        if (sel && selKind) {
          params.set("sel", sel);
          params.set("sel_kind", selKind);
        }
      }
      // graph 활성 시에만 graph params (modeling section 한정)
      if (activeSection === "modeling" && graphActive) {
        params.set("view", "graph");
        if (graphTopMode !== "coverage") params.set("graph_mode", graphTopMode);
        if (graphTopMode === "coverage") {
          // lens 가 기본값(draft+orphan)과 다를 때만 URL 에 노출
          const sorted = [...coverageLenses].sort().join(",");
          if (sorted !== "draft,orphan") params.set("lenses", coverageLenses.join(","));
        }
        if (graphTopMode === "impact" && impactFocusFqn) {
          params.set("impact_focus", impactFocusFqn);
          params.set("impact_kind", impactFocusKind);
          if (impactHops !== 2) params.set("hops", String(impactHops));
          if (impactDirection !== "both") params.set("dir", impactDirection);
        }
        if (graphTopMode === "explore") {
          if (perspectiveId !== null) params.set("p", String(perspectiveId));
          if (graphMode !== "neighborhood") params.set("mode", graphMode);
          if (graphFocus) params.set("focus", graphFocus);
          if (graphTarget) params.set("target", graphTarget);
          if (graphNMax !== 60) params.set("n_max", String(graphNMax));
        }
      }
      const url = params.toString() ? `${pathname}?${params.toString()}` : pathname;
      if (url !== lastUrlRef.current) {
        lastUrlRef.current = url;
        router.replace(url, { scroll: false });
      }
    }, 200);   // debounce — focus drag 등 rapid 변경 흡수
    return () => clearTimeout(handle);
  }, [
    pathname, router, activeSection,
    repoId, graphActive, graphMode, graphFocus, graphTarget, graphNMax, perspectiveId,
    graphTopMode, coverageLenses, impactFocusFqn, impactFocusKind, impactHops, impactDirection,
    selectedActionFqn, selectedCodeTypeFqn, selectedTermFqn, selectedRuleFqn, selectedAnchorId,
  ]);
}
