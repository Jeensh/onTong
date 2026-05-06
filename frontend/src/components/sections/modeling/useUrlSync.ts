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
  const graphCompound  = useWorkbench((s) => s.graphCompound);
  const graphActive    = useWorkbench((s) => s.graphModeActive);
  const perspectiveId  = useWorkbench((s) => s.activePerspectiveId);
  // setters
  const setRepoId             = useWorkbench((s) => s.setRepoId);
  const setGraphMode          = useWorkbench((s) => s.setGraphMode);
  const setGraphCompound      = useWorkbench((s) => s.setGraphCompound);
  const applyGraphState       = useWorkbench((s) => s.applyGraphState);
  const setActivePerspectiveId = useWorkbench((s) => s.setActivePerspectiveId);

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
    const compoundStr = searchParams.get("compound");
    if (compoundStr === "1" || compoundStr === "true") setGraphCompound(true);

    // 섹션 (workspace) — graph view 가 있으면 modeling 자동 진입
    if (section === "wiki" || section === "modeling" || section === "simulation") {
      if (section !== activeSection) setActiveSection(section as SectionId);
    } else if (view === "graph" && activeSection !== "modeling") {
      setActiveSection("modeling" as SectionId);
    }
    if (repo && repo !== repoId) setRepoId(repo);
    if (view === "graph") setGraphMode(true);

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
            if (typeof p.spec.compound === "boolean") setGraphCompound(p.spec.compound);
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
      // graph 활성 시에만 graph params (modeling section 한정)
      if (activeSection === "modeling" && graphActive) {
        params.set("view", "graph");
        if (perspectiveId !== null) params.set("p", String(perspectiveId));
        if (graphMode !== "neighborhood") params.set("mode", graphMode);
        if (graphFocus) params.set("focus", graphFocus);
        if (graphTarget) params.set("target", graphTarget);
        if (graphNMax !== 60) params.set("n_max", String(graphNMax));
        if (graphCompound) params.set("compound", "1");
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
    repoId, graphActive, graphMode, graphFocus, graphTarget, graphNMax, graphCompound, perspectiveId,
  ]);
}
