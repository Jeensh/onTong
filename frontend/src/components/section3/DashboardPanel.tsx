"use client";

/**
 * Section 3 — 진입 대시보드 (Phase 11 rewrite).
 *
 * 이전 구성 제거:
 *  - Neo4j /graph/stats 노드/관계 카드 (모두 0 으로 떨어져서 오해 유발)
 *  - "빠른 진입" 4 카드 (BridgeChat/Sandbox/CodeImpact/DataImpact — Section3Section
 *    에서 이미 nav 숨김 처리한 legacy 진입점)
 *  - amber tip (dev-only 메모)
 *
 * 새 구성 (SQLite ontology.db 실 데이터):
 *  - repo 선택자 (`/api/section3/repos` 의 repo 목록)
 *  - 선택된 repo 의 8-카운트 카드 (actions / code_methods / code_types / terms /
 *    rules / realizations / call_sites / sessions)
 *  - 선택된 repo 로 필터된 "최근 세션" 리스트
 */

import { useEffect, useState } from "react";
import {
  Activity, Search, History, ChevronRight, Database, GitBranch,
  Package, Layers, Boxes, FileCode2, FileSpreadsheet, GitMerge, MessageSquare,
  AlertTriangle,
} from "lucide-react";
import {
  listRepos, type RepoSummary, type RepoCounts,
} from "@/lib/section3/api";
import {
  listSessions, getWarningRates, getZeroCandQueries,
  type SessionSummary, type WarningRatesResponse, type ZeroCandQueryView,
} from "@/lib/section3/multiturn";
import { getWarningMeta } from "@/lib/section3/warning_meta";

interface Props {
  /** 부모(Section3Section)가 관리. chat 으로 propagate 용. */
  selectedRepo?: string | null;
  onRepoChange?: (repo: string) => void;
  /** 최근 세션 클릭 시 multiturn view 로 전환하면서 sid 주입. */
  onOpenSession?: (sid: string) => void;
}

export function DashboardPanel({
  selectedRepo, onRepoChange, onOpenSession,
}: Props) {
  const [repos, setRepos] = useState<RepoSummary[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    listRepos()
      .then((r) => {
        setRepos(r.repos);
        // 처음 fetch 했고 부모가 아직 repo 안 골랐으면 첫 repo 자동 선택
        if (r.repos.length > 0 && !selectedRepo) {
          onRepoChange?.(r.repos[0].repo_id);
        }
      })
      .catch((e) => setErr(String(e)));
  // mount 시 1 회. selectedRepo / onRepoChange 변경에 재호출 안 함.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const current = repos?.find((r) => r.repo_id === selectedRepo) ?? null;

  return (
    <div className="overflow-y-auto h-full">
      <div className="p-6 space-y-6 max-w-5xl">
        <header>
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Activity size={20} className="text-primary" />
            Section 3 — Simulation Dashboard
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            현재 ontology.db 에 적재된 repo 별 실 데이터 + 멀티턴 세션 이력.
          </p>
        </header>

        {err && (
          <div className="text-sm text-red-600 border border-red-200 bg-red-50 rounded p-3">
            repo 로딩 실패: {err}
          </div>
        )}

        {/* repo selector */}
        {repos !== null && repos.length === 0 && (
          <div className="text-sm text-muted-foreground border border-dashed border-border rounded p-4">
            적재된 repo 가 없습니다. modeling 측에서 repo import 후 다시 시도하세요.
          </div>
        )}

        {repos && repos.length > 0 && (
          <RepoSelector
            repos={repos}
            selected={selectedRepo ?? null}
            onSelect={(id) => onRepoChange?.(id)}
          />
        )}

        {/* count cards (repo-scoped) */}
        {current && <RepoCountGrid counts={current.counts} />}

        {/* Phase 16L — integrity_warning 발화율 (운영 metric, repo-scoped) */}
        {selectedRepo && (
          <WarningRatesSection repoId={selectedRepo} />
        )}

        {/* Phase 16O — 0-cand 매핑 갭 query (modeling team 보조 지표) */}
        {selectedRepo && (
          <ZeroCandQueriesSection repoId={selectedRepo} />
        )}

        {/* recent sessions (repo-scoped) */}
        {selectedRepo && (
          <RecentSessionsSection
            repoId={selectedRepo}
            onOpenSession={onOpenSession}
          />
        )}
      </div>
    </div>
  );
}

// ─── Phase 16L — integrity_warning 발화율 section ─────────────────────────
//   (16P refactor: WARNING_META 는 lib/section3/warning_meta 에서 공유)

function WarningRatesSection({ repoId }: { repoId: string }) {
  const [data, setData] = useState<WarningRatesResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setData(null);
    getWarningRates({ repo_id: repoId, limit: 50 })
      .then((r) => { if (alive) { setData(r); setErr(null); } })
      .catch((e) => { if (alive) setErr(String(e)); });
    return () => { alive = false; };
  }, [repoId]);

  return (
    <div>
      <div className="flex items-center justify-between mb-2 gap-3">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1.5">
          <AlertTriangle size={12} />
          모델링 시드 품질 — 최근 50 세션
          <span className="text-[10px] text-muted-foreground font-mono normal-case font-normal">
            · integrity_warning 발화율
          </span>
        </h3>
      </div>

      {err && (
        <div className="text-[11px] text-red-600 mb-2">
          warning rates 로딩 실패: {err}
        </div>
      )}

      {!err && data && data.total_sessions === 0 && (
        <div className="text-[12px] text-muted-foreground border border-dashed border-border rounded p-3 text-center">
          이 repo 에 아직 세션 기록 없음.
        </div>
      )}

      {!err && data && data.total_sessions > 0 && (
        <div className="border border-border rounded p-3 bg-card/50">
          <div className="text-[11px] text-muted-foreground mb-2">
            총 <span className="font-semibold text-foreground">{data.total_sessions}</span> 세션 중 발화:
          </div>
          {Object.keys(data.by_kind).length === 0 ? (
            <div className="text-[12px] text-emerald-700 font-medium">
              ✓ 무결성 경고 0건 — 시드 품질 양호
            </div>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(data.by_kind_pct)
                .sort(([, a], [, b]) => b - a)
                .map(([kind, pct]) => {
                  const meta = getWarningMeta(kind);
                  const Icon = meta.Icon;
                  const n = data.by_kind[kind] ?? 0;
                  return (
                    <span
                      key={kind}
                      title={`${kind} — ${n}/${data.total_sessions} 세션 발화`}
                      className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full border ${meta.cls}`}
                    >
                      <Icon size={11} />
                      {meta.label}
                      <span className="font-mono ml-0.5">{pct}%</span>
                    </span>
                  );
                })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Phase 16O — 0-cand 매핑 갭 query section ────────────────────────────

function ZeroCandQueriesSection({ repoId }: { repoId: string }) {
  const [queries, setQueries] = useState<ZeroCandQueryView[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setQueries(null);
    getZeroCandQueries({ repo_id: repoId, limit: 20 })
      .then((r) => { if (alive) { setQueries(r.queries); setErr(null); } })
      .catch((e) => { if (alive) setErr(String(e)); });
    return () => { alive = false; };
  }, [repoId]);

  return (
    <div>
      <div className="flex items-center justify-between mb-2 gap-3">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1.5">
          <Search size={12} />
          매핑 갭 query — 0 후보 반환
          <span className="text-[10px] text-muted-foreground font-normal normal-case">
            · modeling 시드 보강 가이드
          </span>
        </h3>
      </div>

      {err && (
        <div className="text-[11px] text-red-600 mb-2">
          매핑 갭 로딩 실패: {err}
        </div>
      )}

      {!err && queries !== null && queries.length === 0 && (
        <div className="text-[12px] text-emerald-700 border border-dashed border-emerald-200 rounded p-3 text-center bg-emerald-50/30">
          ✓ 최근 모든 query 가 후보 매칭 — 시드 커버리지 양호
        </div>
      )}

      {!err && queries && queries.length > 0 && (
        <div className="border border-border rounded divide-y divide-border/50 bg-card/50 max-h-72 overflow-y-auto">
          {queries.map((q) => (
            <div key={q.session_id} className="px-3 py-2 hover:bg-muted/30">
              <div className="flex items-baseline gap-2">
                <span className="text-[12px] font-medium truncate flex-1">
                  &quot;{q.user_query}&quot;
                </span>
                <span className="text-[10px] text-muted-foreground font-mono shrink-0">
                  {new Date(q.created_at).toLocaleString("ko-KR", {
                    month: "2-digit", day: "2-digit",
                    hour: "2-digit", minute: "2-digit",
                  })}
                </span>
              </div>
              {q.suggestions.length > 0 && (
                <div className="text-[10px] text-muted-foreground/80 mt-0.5">
                  agent 제안: {q.suggestions.slice(0, 3).join(", ")}
                  {q.suggestions.length > 3 && ` +${q.suggestions.length - 3}`}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Repo selector ────────────────────────────────────────────────────────

function RepoSelector({
  repos, selected, onSelect,
}: {
  repos: RepoSummary[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1">
        <GitBranch size={11} /> Repo
      </span>
      {repos.map((r) => {
        const active = r.repo_id === selected;
        return (
          <button
            key={r.repo_id}
            onClick={() => onSelect(r.repo_id)}
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-mono transition-colors ${
              active
                ? "bg-primary text-primary-foreground border-primary"
                : "bg-card text-foreground border-border hover:border-primary/40"
            }`}
          >
            {r.repo_id}
            <span
              className={`text-[10px] ${
                active ? "text-primary-foreground/80" : "text-muted-foreground"
              }`}
            >
              · {r.counts.code_methods}m / {r.counts.actions}a / {r.counts.sessions}s
            </span>
          </button>
        );
      })}
    </div>
  );
}

// ─── Count cards ──────────────────────────────────────────────────────────

const COUNT_DEFS: Array<{
  key: keyof RepoCounts;
  label: string;
  desc: string;
  icon: React.ReactNode;
  tone: string;
}> = [
  { key: "actions",        label: "Actions",        desc: "Ontology action",                icon: <Package size={14} />,         tone: "border-blue-300    bg-blue-50    text-blue-700" },
  { key: "code_methods",   label: "Code Methods",   desc: "Java method 본문",                icon: <FileCode2 size={14} />,       tone: "border-emerald-300 bg-emerald-50 text-emerald-700" },
  { key: "code_types",     label: "Code Types",     desc: "Class / Interface / Record",      icon: <Boxes size={14} />,           tone: "border-cyan-300    bg-cyan-50    text-cyan-700" },
  { key: "business_terms", label: "Business Terms", desc: "도메인 용어",                      icon: <Layers size={14} />,          tone: "border-pink-300    bg-pink-50    text-pink-700" },
  { key: "business_rules", label: "Business Rules", desc: "도메인 규칙",                      icon: <FileSpreadsheet size={14} />, tone: "border-amber-300   bg-amber-50   text-amber-700" },
  { key: "realizations",   label: "Realizations",   desc: "Action ↔ Method 매핑",            icon: <GitMerge size={14} />,        tone: "border-violet-300  bg-violet-50  text-violet-700" },
  { key: "call_sites",     label: "Call Sites",     desc: "메소드 호출 그래프 edge",          icon: <Database size={14} />,        tone: "border-orange-300  bg-orange-50  text-orange-700" },
  { key: "sessions",       label: "Chat Sessions",  desc: "멀티턴 누적 세션",                 icon: <MessageSquare size={14} />,   tone: "border-slate-300   bg-slate-50   text-slate-700" },
];

function RepoCountGrid({ counts }: { counts: RepoCounts }) {
  return (
    <div>
      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
        📦 적재 데이터 (선택 repo)
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        {COUNT_DEFS.map((d) => {
          const n = counts[d.key];
          return (
            <div key={d.key} className={`rounded-lg border-2 p-3 ${d.tone}`}>
              <div className="flex items-center gap-2 mb-1.5">
                {d.icon}
                <span className="text-[11px] font-semibold">{d.label}</span>
              </div>
              <div className="text-2xl font-bold">{n.toLocaleString()}</div>
              <div className="text-[10px] opacity-70 mt-1">{d.desc}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Recent multiturn sessions (repo-scoped) ──────────────────────────────

function RecentSessionsSection({
  repoId, onOpenSession,
}: { repoId: string; onOpenSession?: (sid: string) => void }) {
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    let alive = true;
    setSessions(null);
    const t = setTimeout(() => {
      listSessions({
        limit: 20,
        repo_id: repoId,
        search: search.trim() || undefined,
      })
        .then((r) => { if (alive) { setSessions(r.sessions); setErr(null); } })
        .catch((e) => { if (alive) setErr(String(e)); });
    }, search ? 200 : 0);
    return () => { alive = false; clearTimeout(t); };
  }, [repoId, search]);

  return (
    <div>
      <div className="flex items-center justify-between mb-2 gap-3">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1.5">
          <History size={12} />
          최근 세션 {sessions ? `(${sessions.length})` : ""}
          <span className="text-[10px] text-muted-foreground font-mono normal-case font-normal">
            · {repoId}
          </span>
        </h3>
        <div className="relative">
          <Search size={11} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="검색 (user_query)"
            className="text-[11px] pl-6 pr-2 py-1 border border-border rounded bg-background w-48 focus:outline-none focus:border-primary"
          />
        </div>
      </div>

      {err && (
        <div className="text-[11px] text-red-600 mb-2">
          최근 세션 로딩 실패: {err}
        </div>
      )}

      {!err && sessions !== null && sessions.length === 0 && (
        <div className="text-[12px] text-muted-foreground border border-dashed border-border rounded p-3 text-center">
          {search ? (
            <>"{search}" 매칭 세션 없음</>
          ) : (
            <>이 repo 에 아직 멀티턴 세션이 없습니다. 멀티턴 메뉴에서 첫 질문을 시작해보세요.</>
          )}
        </div>
      )}

      {!err && sessions && sessions.length > 0 && (
        <div className="space-y-1.5">
          {sessions.map((s) => (
            <SessionRow
              key={s.id}
              session={s}
              onClick={() => onOpenSession?.(s.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function SessionRow({
  session, onClick,
}: { session: SessionSummary; onClick: () => void }) {
  const ts = new Date(session.last_activity_at);
  const tsLabel = `${ts.getFullYear().toString().slice(2)}-${pad2(ts.getMonth() + 1)}-${pad2(ts.getDate())} ${pad2(ts.getHours())}:${pad2(ts.getMinutes())}`;
  const statusTone =
    session.status === "done"    ? "text-emerald-600 bg-emerald-50 border-emerald-200" :
    session.status === "blocked" ? "text-rose-600   bg-rose-50   border-rose-200"    :
                                  "text-amber-600  bg-amber-50  border-amber-200";
  const gateLabel = GATE_LABEL[session.last_gate_kind ?? ""] ?? session.last_gate_kind ?? "—";

  return (
    <button
      onClick={onClick}
      className="w-full text-left rounded border border-border bg-card hover:border-primary/40 hover:bg-muted/40 transition-colors p-2 flex items-center gap-3"
    >
      <div className="flex flex-col items-start gap-0.5 min-w-0 flex-1">
        <div className="flex items-center gap-2 text-[11px] font-mono text-muted-foreground">
          <span>{tsLabel}</span>
          <span className={`px-1.5 py-px rounded border ${statusTone}`}>
            {session.status}
          </span>
          <span className="text-[10px] text-muted-foreground">
            {session.turn_count} turns
          </span>
          <span className="text-[10px] text-blue-600">{gateLabel}</span>
        </div>
        <div className="text-[12px] text-foreground truncate w-full">
          {session.user_query || <span className="italic text-muted-foreground">(no query)</span>}
        </div>
        <div className="text-[10px] text-muted-foreground font-mono">
          {session.id.slice(0, 8)}
        </div>
      </div>
      <ChevronRight size={14} className="text-muted-foreground shrink-0" />
    </button>
  );
}

const GATE_LABEL: Record<string, string> = {
  target_selected:     "Gate I",
  bundle_prepared:     "Gate II",
  executed_simulation: "Gate III · sim",
  executed_impact:     "Gate III · impact",
};

function pad2(n: number): string { return String(n).padStart(2, "0"); }
