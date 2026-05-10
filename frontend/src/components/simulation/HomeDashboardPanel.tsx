"use client";

import { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  BookMarked,
  CheckCircle2,
  Database,
  GitCompare,
  Layers,
  Network,
  Sparkles,
  Target,
  TrendingUp,
  Zap,
} from "lucide-react";
import { listJobs, listRuns, listScenarios } from "@/lib/simulation/storageApi";
import { DbSeedCard } from "./DbSeedCard";
import { MigrationDiffCard } from "./MigrationDiffCard";
import { OntologyEvidenceToggle } from "./OntologyEvidencePanel";

interface Props {
  onJump?: (view: string) => void;
}

interface Kpi {
  totalRuns: number;
  totalScenarios: number;
  baselineRuns: number;
  jobsDone: number;
  regressionsWithDiff: number;
}

const PAIN_POINTS = [
  {
    icon: <AlertTriangle size={18} className="text-amber-500" />,
    title: "룰 1줄 변경의 영향이 안 보임",
    body: "비표준 컬럼명 (PRODUCT_TYPE_CD vs PRODUCT_NAME_CD vs PROD_KIND_CD), 4-deep 중첩 if, reflection JPO 매핑 — 정적 분석으로 영향 범위 파악 어려움.",
  },
  {
    icon: <Database size={18} className="text-amber-500" />,
    title: "테스트 환경 부재",
    body: "21-step 알고리즘 검증을 위해 자바 빌드 + Oracle DB + Kafka 가 필요. 운영자가 'rule 0.95 → 0.92로 바꿔보자' 손쉽게 시도 불가.",
  },
  {
    icon: <Target size={18} className="text-amber-500" />,
    title: "회귀 검증의 추적성 부재",
    body: "\"이 fix 가 baseline 과 같은 결과인가?\" 검증을 매번 수작업. 결과 변동 fan-out 시각화 없음.",
  },
];

const BEFORE_AFTER = [
  {
    title: "룰 변경 영향 시뮬",
    before: "자바 풀 빌드 + 테스트 셋업 (수 시간)",
    after: "Hypothesis 100건 자동 생성 + Python 격리 실행 (수 초)",
    metric: "★ 시간 단축",
  },
  {
    title: "코드 커버리지",
    before: "정적 도구 — \"가능한 분기\" 만",
    after: "Risk Heatmap — \"실제 비즈니스 데이터로 도달한 빈도\" (라인별)",
    metric: "★ 동적 커버리지",
  },
  {
    title: "테스트 케이스 작성",
    before: "사람이 직접 정상/경계/오류 케이스 설계",
    after: "도메인 용어 → AI 자동 추천 (OntologyBridge)",
    metric: "★ 자동화",
  },
  {
    title: "재실행 비교 (수정 안전성 검증)",
    before: "수동 비교, 추적 안됨",
    after: "기준 결과 저장 → 같은 시나리오 재실행 시 자동 차이 검증 + 양방향 추적",
    metric: "★ 추적성",
  },
];

const REUSE_VALUE = [
  {
    icon: <Layers size={16} className="text-primary" />,
    title: "다른 도메인 자동 편입",
    body: "Java→Python transpile 모듈 (tree-sitter + LLM + 동치성 검증) 로 새 자바 시스템의 메서드를 시뮬 단계로 자동 변환. step 인터페이스/Hypothesis/RiskHeatmap 은 도메인 무관 인프라.",
  },
  {
    icon: <BookMarked size={16} className="text-primary" />,
    title: "시나리오 라이브러리 공유",
    body: "YAML 시나리오 export/import 로 팀 간 공유. 운영 노하우가 자동 회귀 자산으로 누적.",
  },
  {
    icon: <Network size={16} className="text-primary" />,
    title: "Section 1·2와의 통합",
    body: "Wiki 의 ImageProcessingQueue 패턴 미러 + Modeling 의 ontology 결합. 3-Section 한 플랫폼으로 운영지식 → 모델 → 시뮬 → 검증 루프.",
  },
];

interface MigOutput {
  before: { castCd?: string; machineCd?: string; thickness?: string | null } | null;
  after: { castCd?: string; machineCd?: string; thickness?: string | null } | null;
  changed: boolean;
}

export function HomeDashboardPanel({ onJump }: Props = {}) {
  const [kpi, setKpi] = useState<Kpi | null>(null);
  const [migOut, setMigOut] = useState<MigOutput | null>(null);
  const [migLoading, setMigLoading] = useState(false);
  const [migInputs, setMigInputs] = useState<Record<string, unknown>>({
    smCd: "K",
    productTypeCd: "A001",
    mapping_overrides: { K: { castCd: "CC2", machineCd: "M2" } },
  });

  const runMigDemo = async () => {
    setMigLoading(true);
    try {
      const r = await fetch("/api/simulation/jobs/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ step_id: "plant_mapping_migrate", inputs: migInputs }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const job = await r.json();
      // 잡 완료까지 폴링 (보통 1ms 내)
      for (let i = 0; i < 30; i++) {
        await new Promise((res) => setTimeout(res, 100));
        const j = await fetch(`/api/simulation/jobs/${job.id}`).then((x) => x.json());
        if (j.status === "done" && j.outputs) {
          setMigOut(j.outputs as MigOutput);
          break;
        }
        if (j.status === "failed") {
          break;
        }
      }
    } catch (e) {
      console.error(e);
    } finally {
      setMigLoading(false);
    }
  };

  useEffect(() => {
    const load = async () => {
      const [scnsRaw, runsRaw, jobsRaw] = await Promise.all([
        listScenarios().catch(() => []),
        listRuns({ limit: 200 }).catch(() => []),
        listJobs(200).catch(() => []),
      ]);
      const scns = Array.isArray(scnsRaw) ? scnsRaw : [];
      const runs = Array.isArray(runsRaw) ? runsRaw : [];
      const jobs = Array.isArray(jobsRaw) ? jobsRaw : [];
      const baseline = runs.filter((r) => r.is_baseline).length;
      const jobsDone = jobs.filter((j) => j.status === "done").length;
      const regressionsWithDiff = jobs.filter(
        (j) => j.regression && (j.regression.diff_count ?? 0) > 0
      ).length;
      setKpi({
        totalRuns: runs.length,
        totalScenarios: scns.length,
        baselineRuns: baseline,
        jobsDone,
        regressionsWithDiff,
      });
    };
    load();
    const id = setInterval(load, 8000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="space-y-5">
      {/* ── 히어로 ─────────────────────────────────────── */}
      <div className="rounded-lg border border-primary/20 bg-gradient-to-br from-primary/5 via-card to-card p-5">
        <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
          <Zap size={24} className="text-primary" />
          Section 3 — 코드 기반 온톨로지 시뮬레이션
        </h1>
        <p className="text-sm text-muted-foreground mt-1.5 leading-relaxed max-w-4xl">
          자바 시스템 (slab-design 21단계 알고리즘) 의 코드를 분석해 도메인 그래프(온톨로지) 를
          만들고, 그 위에서 룰 한 줄 변경 결과를 자바 빌드 없이 파이썬으로 실제 실행해 보여주는
          시뮬레이션 플랫폼. 운영 노하우는 시나리오 라이브러리로 누적되고, 「기준 결과」와 자동
          비교되어 회귀를 검증합니다.
        </p>
      </div>

      {/* ── DB 시드 카드 (PG 활성 시 9 마스터 + 5 샘플 주문 적재) ── */}
      <DbSeedCard />

      {/* ── 온톨로지 근거 — Section 2 ontology trace ─────────── */}
      <OntologyEvidenceToggle
        actionFqn="action.scm.슬랩설계_실행"
        label="📚 이 시뮬레이션 플랫폼의 온톨로지 근거 (Section 2 → Section 3)"
      />

      {/* ── 핵심 지표 ─────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label="등록 시나리오" value={kpi?.totalScenarios ?? "—"} hint="라이브러리 + 사용자 추가" tone="primary" />
        <KpiCard label="누적 실행" value={kpi?.totalRuns ?? "—"} hint="격리된 안전 환경에서 실행" tone="emerald" />
        <KpiCard label="기준 결과 저장" value={kpi?.baselineRuns ?? "—"} hint="비교 기준이 되는 실행" tone="amber" />
        <KpiCard label="차이 발견" value={kpi?.regressionsWithDiff ?? "—"} hint="기준과 달라진 실행 수" tone="red" />
      </div>

      {/* ── 빠른 시작 (먼저 보여줌 — 처음 들어온 사용자가 행동하기 좋게) ── */}
      <Section
        title="어디로 갈까요?"
        subtitle="자주 쓰는 6가지 — 카드 클릭으로 바로 이동"
        icon={<Sparkles size={18} className="text-amber-500" />}
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
          <QuickAction
            n="1" title="시나리오 라이브러리" desc="등록된 8건 시나리오 중 'HR 실수율 0.95→0.92' 1-click 실행"
            target="scenarios" onJump={onJump}
          />
          <QuickAction
            n="2" title="실행 이력" desc="방금 실행한 결과를 「기준 결과」로 저장"
            target="history" onJump={onJump}
          />
          <QuickAction
            n="3" title="안전 가상 실행 (샌드박스)" desc="테스트 케이스 100건 자동 + 라인별 위험도 색칠"
            target="sandbox" onJump={onJump}
          />
          <QuickAction
            n="4" title="재실행 비교 (차이 검증)" desc="기준 결과 vs 새 실행 결과 필드 단위 비교"
            target="regression" onJump={onJump}
            icon={<GitCompare size={14} />}
          />
          <QuickAction
            n="5" title="온톨로지 브릿지" desc='"실수율" 검색 → 영향 step + 추천 시나리오'
            target="bridge" onJump={onJump}
          />
          <QuickAction
            n="6" title="변경 영향 분석" desc="룰 변경 전·후 결과 분포 + Cascade 흐름도"
            target="impact" onJump={onJump}
          />
        </div>
      </Section>

      {/* ── 라이브 데모 (full width 강조) ─────────────── */}
      <Section
        title="🚀 라이브 데모 — PlantMapping 마이그"
        subtitle="레거시 하드코딩 매핑이 바뀌면 어느 주문이 깨지는지 1-click 으로 보여줍니다"
        icon={<Sparkles size={18} className="text-amber-500" />}
      >
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4 space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-xs">
            <p className="text-muted-foreground">
              입력: <span className="font-mono text-foreground">smCd={String(migInputs.smCd)}</span> ·{" "}
              <span className="font-mono text-foreground">productType={String(migInputs.productTypeCd)}</span> · 마이그 후{" "}
              <span className="font-mono text-foreground">K → CC2/M2</span>
            </p>
            <button
              onClick={runMigDemo}
              disabled={migLoading}
              className="inline-flex items-center gap-1 rounded bg-primary text-primary-foreground px-3 py-1.5 text-xs font-medium disabled:opacity-50 self-start sm:self-auto"
            >
              {migLoading ? "실행 중..." : "지금 실행"}
            </button>
          </div>
          <MigrationDiffCard output={migOut} inputs={migInputs} />
        </div>
      </Section>

      {/* ── 좌우 2열: 페인포인트 + Before/After ──────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Section
          title="왜 이 시스템이 필요한가"
          subtitle="현재의 페인포인트 3가지"
          icon={<AlertTriangle size={18} className="text-amber-500" />}
        >
          <div className="space-y-2.5">
            {PAIN_POINTS.map((p) => (
              <div
                key={p.title}
                className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 space-y-1"
              >
                <div className="flex items-center gap-1.5">
                  {p.icon}
                  <h4 className="text-sm font-semibold text-foreground">{p.title}</h4>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">{p.body}</p>
              </div>
            ))}
          </div>
        </Section>

        <Section
          title="무엇이 달라졌는가"
          subtitle="Before / After 비교 4가지"
          icon={<TrendingUp size={18} className="text-emerald-500" />}
        >
          <div className="space-y-2.5">
            {BEFORE_AFTER.map((b) => (
              <div
                key={b.title}
                className="rounded-lg border border-border bg-card p-3 space-y-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <h4 className="text-sm font-semibold text-foreground">{b.title}</h4>
                  <span className="rounded bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 px-1.5 py-0.5 text-[10px] font-medium whitespace-nowrap">
                    {b.metric}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div className="rounded border border-red-500/20 bg-red-500/5 p-2">
                    <p className="text-[9px] uppercase tracking-wider text-red-700 dark:text-red-300 font-semibold mb-1">
                      Before
                    </p>
                    <p className="text-muted-foreground">{b.before}</p>
                  </div>
                  <div className="rounded border border-emerald-500/20 bg-emerald-500/5 p-2">
                    <p className="text-[9px] uppercase tracking-wider text-emerald-700 dark:text-emerald-300 font-semibold mb-1">
                      After
                    </p>
                    <p className="text-foreground">{b.after}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Section>
      </div>

      {/* ── 좌우 2열: 확산 가치 + 적용 기술 ──────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Section
          title="어떻게 확산되는가"
          subtitle="재사용성 / 확장성 / 공유가치"
          icon={<Layers size={18} className="text-primary" />}
        >
          <div className="space-y-2.5">
            {REUSE_VALUE.map((r) => (
              <div
                key={r.title}
                className="rounded-lg border border-primary/20 bg-primary/5 p-3 space-y-1"
              >
                <div className="flex items-center gap-1.5">
                  {r.icon}
                  <h4 className="text-sm font-semibold text-foreground">{r.title}</h4>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">{r.body}</p>
              </div>
            ))}
          </div>
        </Section>

        <Section
          title="적용된 기술"
          subtitle="Backend · Frontend · AI · 통합"
          icon={<CheckCircle2 size={18} className="text-emerald-500" />}
        >
          <div className="rounded-lg border border-border bg-card p-3 space-y-2 text-[11px] leading-relaxed">
            <TechRow label="Backend">
              FastAPI + Pydantic + SQLite (시나리오 / run / lineage) ·
              <span className="font-mono text-primary"> subprocess + resource.setrlimit</span> (격리 실행) ·
              <span className="font-mono text-primary"> Hypothesis 6.x</span> (테스트 케이스 자동) ·
              <span className="font-mono text-primary"> asyncio Semaphore Job Queue</span>.
            </TechRow>
            <TechRow label="Frontend">
              Next.js 15 (turbopack) + shadcn 토큰 + lucide 아이콘 +
              <span className="font-mono text-primary"> Plotly</span> (위험도 히트맵 / Cascade / 분포) + fetch 기반 SSE.
            </TechRow>
            <TechRow label="AI">
              <span className="font-mono text-primary">Pydantic AI tool-use</span> 로 자연어 ("HR 실수율 0.85로 줄이면?") → 시나리오 자동 변환.
              OntologyBridge 카탈로그 16종 fallback. <span className="font-mono text-primary">tree-sitter + LLM</span> 으로 Java→Python 자동 변환 인프라 (관리자용).
            </TechRow>
            <TechRow label="통합">
              Section 2 ontology client 결합 (Neo4j BFS, graceful timeout fallback). Wiki 의 fire-and-forget 패턴 미러. 183건 pytest + tsc exit 0.
            </TechRow>
          </div>
        </Section>
      </div>

      <div className="text-[10px] text-muted-foreground/60 text-center pt-4 border-t border-border">
        대상 코드베이스: <span className="font-mono">sample-repos/slab-design</span> (Java/Spring Boot 21단계 Slab 설계 알고리즘) ·
        코드 기반 온톨로지 시뮬레이션 플랫폼.
      </div>
    </div>
  );
}

function TechRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <p>
      <span className="inline-block rounded bg-muted/60 text-foreground font-semibold px-1.5 py-0.5 text-[10px] mr-1.5">
        {label}
      </span>
      <span className="text-muted-foreground">{children}</span>
    </p>
  );
}

function KpiCard({ label, value, hint, tone }: {
  label: string; value: number | string; hint: string;
  tone: "primary" | "emerald" | "amber" | "red";
}) {
  const tones = {
    primary: "border-primary/20 bg-primary/5 text-primary",
    emerald: "border-emerald-500/20 bg-emerald-500/5 text-emerald-600 dark:text-emerald-400",
    amber: "border-amber-500/20 bg-amber-500/5 text-amber-600 dark:text-amber-400",
    red: "border-red-500/20 bg-red-500/5 text-red-600 dark:text-red-400",
  } as const;
  return (
    <div className={`rounded-lg border ${tones[tone]} p-3 space-y-0.5`}>
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">{label}</p>
      <p className="text-2xl font-bold tabular-nums">{value}</p>
      <p className="text-[10px] text-muted-foreground">{hint}</p>
    </div>
  );
}

function Section({ title, subtitle, icon, children }: {
  title: string; subtitle: string; icon: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <section className="space-y-2">
      <div className="flex items-baseline gap-2">
        {icon}
        <h2 className="text-base font-semibold text-foreground">{title}</h2>
        <span className="text-[11px] text-muted-foreground">{subtitle}</span>
      </div>
      {children}
    </section>
  );
}

function QuickAction({ n, title, desc, target, onJump, icon }: {
  n: string; title: string; desc: string;
  target: string; onJump?: (v: string) => void;
  icon?: React.ReactNode;
}) {
  return (
    <button
      onClick={() => onJump?.(target)}
      className="flex items-start gap-2 rounded-lg border border-border bg-card p-3 text-left hover:border-primary/40 hover:bg-primary/5 transition-colors"
    >
      <span className="rounded-full bg-primary/10 text-primary text-xs font-bold w-6 h-6 flex items-center justify-center flex-shrink-0">
        {n}
      </span>
      <div className="flex-1 min-w-0">
        <h4 className="text-sm font-semibold text-foreground flex items-center gap-1">
          {icon} {title}
        </h4>
        <p className="text-[11px] text-muted-foreground mt-0.5">{desc}</p>
      </div>
      <ArrowRight size={14} className="text-muted-foreground flex-shrink-0 mt-1" />
    </button>
  );
}
