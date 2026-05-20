"use client";

import { useEffect, useRef, useState } from "react";
import { FolderInput, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  API_BASE,
  ontologyApi,
  type RecommendationResponseDTO,
  type RepoImportStatusDTO,
} from "@/lib/api/ontology";
import { useWorkbench } from "./store";

type Phase = "form" | "importing" | "recommending" | "done" | "error";

export function RepoImportModal({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const setRepoId = useWorkbench((s) => s.setRepoId);

  const [repoPath, setRepoPath] = useState("sample-repos/slab-design-real_v2");
  const [repoId, setRepoIdInput] = useState("slab-design-real-v2");
  const [repoIdManuallyEdited, setRepoIdManuallyEdited] = useState(false);
  const [phase, setPhase] = useState<Phase>("form");
  const [status, setStatus] = useState<RepoImportStatusDTO | null>(null);
  const [recommendation, setRecommendation] = useState<RecommendationResponseDTO | null>(null);
  const [error, setError] = useState<string | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);

  // 자동 repo_id 추출 — path basename. underscore/특수문자 → dash 로 normalize
  // (sim_v2 테스트 & handoff DB 가 dash 컨벤션이라 충돌 방지).
  // 사용자가 직접 편집했으면 더 이상 덮어쓰지 않음.
  useEffect(() => {
    if (phase !== "form") return;
    if (repoIdManuallyEdited) return;
    const last = repoPath.split("/").filter(Boolean).pop();
    if (last) {
      const normalized = last.replace(/[_\s]+/g, "-").replace(/[^a-zA-Z0-9-]/g, "-");
      setRepoIdInput(normalized);
    }
  }, [repoPath, phase, repoIdManuallyEdited]);

  // 모달 닫힐 때 SSE 정리
  useEffect(() => {
    if (!open) {
      cleanupRef.current?.();
      cleanupRef.current = null;
      // form 으로 reset (5초 후 다시 시작 가능하도록)
      if (phase === "done" || phase === "error") {
        setTimeout(() => {
          setPhase("form");
          setStatus(null);
          setRecommendation(null);
          setError(null);
        }, 200);
      }
    }
    return () => {
      cleanupRef.current?.();
    };
  }, [open, phase]);

  async function handleStart() {
    if (!repoPath.trim() || !repoId.trim()) {
      setError("repo_path 와 repo_id 모두 필요합니다");
      return;
    }
    setError(null);
    setPhase("importing");
    try {
      const job = await ontologyApi.startRepoImport(repoId.trim(), repoPath.trim());
      cleanupRef.current = ontologyApi.streamRepoImportProgress(
        job.job_id,
        (s, eventType) => {
          setStatus(s);
          if (eventType === "end") {
            if (s.status === "error") {
              setPhase("error");
              setError(s.message || s.errors[0] || "import 실패");
            } else {
              // import done → 자동으로 recommend persist
              void runRecommend(repoId.trim());
            }
          }
        },
        (err) => {
          // SSE 끊김 — status poll fallback
          console.warn("[repo-import] SSE error, falling back to poll", err);
          void pollUntilDone(job.job_id);
        },
      );
    } catch (e) {
      setPhase("error");
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function pollUntilDone(jobId: string) {
    while (true) {
      try {
        const s = await ontologyApi.getRepoImportStatus(jobId);
        setStatus(s);
        if (s.status === "done") {
          void runRecommend(s.repo_id);
          return;
        }
        if (s.status === "error") {
          setPhase("error");
          setError(s.message || "import 실패");
          return;
        }
      } catch {
        // 잠시 무시 — 다음 poll 에서 재시도
      }
      await new Promise((r) => setTimeout(r, 500));
    }
  }

  async function runRecommend(activeRepoId: string) {
    setPhase("recommending");
    try {
      const rec = await ontologyApi.recommendForRepo(activeRepoId, { persist: true });
      setRecommendation(rec);
      setPhase("done");
      // 워크벤치 활성 repo 갱신
      setRepoId(activeRepoId);
    } catch (e) {
      setPhase("error");
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const showProgress = phase === "importing" || phase === "recommending";
  const pct = phase === "recommending" ? 100 : (status?.progress_pct ?? 0);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FolderInput className="w-4 h-4" />
            Java Repo Import
          </DialogTitle>
          <DialogDescription className="text-xs">
            Java 프로젝트를 분석해 CodeType / Method / CallSite 를 추출하고, 자동으로 BusinessTerm /
            Action / TypeRealization 후보를 큐에 등록합니다.
          </DialogDescription>
        </DialogHeader>

        {/* Form */}
        {phase === "form" && (
          <div className="space-y-3">
            <label className="block">
              <span className="text-xs text-muted-foreground mb-1 block">Repo path (절대/상대)</span>
              <Input
                value={repoPath}
                onChange={(e) => setRepoPath(e.target.value)}
                placeholder="sample-repos/slab-design-real_v2"
                className="font-mono text-xs"
              />
            </label>
            <label className="block">
              <span className="text-xs text-muted-foreground mb-1 block">Repo ID (저장 키)</span>
              <Input
                value={repoId}
                onChange={(e) => {
                  setRepoIdInput(e.target.value);
                  setRepoIdManuallyEdited(true);
                }}
                className="font-mono text-xs"
              />
              <span className="text-[10px] text-muted-foreground mt-1 block">
                같은 ID 재사용 시 기존 데이터를 깨끗하게 교체합니다 (idempotent).
              </span>
            </label>
            {error && (
              <div className="text-xs text-destructive flex items-center gap-1">
                <AlertCircle className="w-3 h-3" /> {error}
              </div>
            )}
          </div>
        )}

        {/* Progress */}
        {showProgress && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm">
              <Loader2 className="w-4 h-4 animate-spin text-primary" />
              <span className="font-medium">
                {phase === "recommending"
                  ? "자동 매핑 추천 생성 중..."
                  : phaseLabel(status?.status ?? "pending")}
              </span>
            </div>
            <div className="h-2 bg-muted rounded overflow-hidden">
              <div
                className="h-full bg-primary transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>
            <div className="text-xs text-muted-foreground font-mono">
              {status && (
                <>
                  <div>{status.message}</div>
                  <div className="mt-1 grid grid-cols-2 gap-x-4">
                    <span>files: {status.files_parsed} / {status.files_total}</span>
                    <span>{status.duration_ms}ms</span>
                    {status.types_extracted > 0 && (
                      <>
                        <span>CodeType: {status.types_extracted}</span>
                        <span>Method: {status.methods_extracted}</span>
                        <span>CallSite: {status.call_sites_extracted}</span>
                      </>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* Done */}
        {phase === "done" && status && recommendation && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-emerald-600">
              <CheckCircle2 className="w-4 h-4" />
              Import + 자동 매핑 완료 ({status.duration_ms}ms)
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <StatCard label="CodeType" value={status.types_extracted} />
              <StatCard label="Method" value={status.methods_extracted} />
              <StatCard label="CallSite" value={status.call_sites_extracted} />
            </div>
            <div className="border-t border-border pt-3">
              <div className="text-xs font-medium mb-2">자동 추천 큐 (confirmed=False)</div>
              <div className="grid grid-cols-3 gap-2 text-xs">
                <StatCard label="BusinessTerm" value={recommendation.summary.terms} accent />
                <StatCard label="Action" value={recommendation.summary.actions} accent />
                <StatCard label="Realization" value={recommendation.summary.type_realizations} accent />
              </div>
              <div className="text-[11px] text-muted-foreground mt-2">
                매핑 큐 탭에서 confirm / reject / 편집할 수 있습니다.
              </div>
            </div>
          </div>
        )}

        {/* Error */}
        {phase === "error" && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-destructive">
              <AlertCircle className="w-4 h-4" /> 실패
            </div>
            <pre className="text-[11px] font-mono text-destructive bg-destructive/5 p-2 rounded border border-destructive/20 max-h-40 overflow-auto whitespace-pre-wrap">
              {error}
            </pre>
            {isLikelyNetworkError(error) && (
              <div className="text-[11px] text-muted-foreground bg-muted/40 border border-border rounded p-2 space-y-1">
                <div className="font-medium text-foreground">백엔드 연결 진단</div>
                <div>
                  API_BASE: <code className="font-mono">{API_BASE}</code>
                </div>
                <div className="text-[10px]">
                  • 백엔드가 위 주소에서 실행 중인지 확인 (<code>curl {API_BASE}/docs</code>)
                  <br />
                  • 다른 포트 사용 중이면 <code>frontend/.env.local</code> 의 <code>NEXT_PUBLIC_API_BASE_URL</code> 수정 후 <strong>Next dev 재시작</strong>
                  <br />
                  • CORS 허용 origin 은 localhost:3000/3001 + 127.0.0.1:3000/3001
                </div>
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          {phase === "form" && (
            <Button onClick={handleStart} disabled={!repoPath.trim() || !repoId.trim()}>
              Import 시작
            </Button>
          )}
          {(phase === "done" || phase === "error") && (
            <Button onClick={() => onOpenChange(false)}>닫기</Button>
          )}
          {showProgress && (
            <Button variant="outline" disabled>
              진행 중...
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function isLikelyNetworkError(msg: string | null): boolean {
  if (!msg) return false;
  const low = msg.toLowerCase();
  return (
    low.includes("failed to fetch") ||
    low.includes("networkerror") ||
    low.includes("load failed") ||
    low.includes("err_connection") ||
    low.includes("err_network")
  );
}


function phaseLabel(s: string): string {
  switch (s) {
    case "pending":     return "대기 중";
    case "parsing":     return "Java 파싱 중";
    case "adapting":    return "CodeType 매핑 중";
    case "classifying": return "Role 분류 중";
    case "storing":     return "SQLite 저장 중";
    case "done":        return "완료";
    case "error":       return "오류";
    default:            return s;
  }
}

function StatCard({
  label, value, accent = false,
}: { label: string; value: number; accent?: boolean }) {
  return (
    <div className={
      "rounded border px-2 py-1.5 " +
      (accent
        ? "border-primary/40 bg-primary/5"
        : "border-border bg-card")
    }>
      <div className="text-[10px] text-muted-foreground">{label}</div>
      <div className={"font-mono text-sm font-semibold " + (accent ? "text-primary" : "")}>
        {value.toLocaleString()}
      </div>
    </div>
  );
}
