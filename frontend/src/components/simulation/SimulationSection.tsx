"use client";

import { useEffect, useState } from "react";
import {
  Beaker,
  BookMarked,
  Compass,
  Flame,
  GitCompare,
  History,
  Home,
  Link2,
  Settings2,
  Zap,
} from "lucide-react";
import { ImpactPanel } from "./ImpactPanel";
import { SandboxPanel } from "./SandboxPanel";
import { NavigatorPanel } from "./NavigatorPanel";
import { ScenarioLibraryPanel } from "./ScenarioLibraryPanel";
import { RunHistoryPanel } from "./RunHistoryPanel";
import { RegressionPanel } from "./RegressionPanel";
import { OntologyBridgePanel } from "./OntologyBridgePanel";
import { HomeDashboardPanel } from "./HomeDashboardPanel";
import { OnboardingBanner } from "./OnboardingBanner";
import { JavaPythonComparePanel } from "./JavaPythonComparePanel";

type SimView =
  | "home"
  | "sandbox"
  | "scenarios"
  | "history"
  | "regression"
  | "impact"
  | "navigator"
  | "bridge"
  | "differential";

interface NavItem {
  id: SimView;
  label: string;
  icon: React.ReactNode;
  description: string;
  /** 사이드바 hover 시 추가로 보여줄 긴 설명 (툴팁). */
  tooltip?: string;
}

const HOME_NAV: NavItem[] = [
  {
    id: "home",
    label: "홈 (개요)",
    icon: <Home size={18} />,
    description: "시스템 소개 + 핵심 지표",
    tooltip: "처음 오셨다면 여기. 왜 이 시스템이 있고 무엇을 할 수 있는지 + 최근 사용 통계.",
  },
];

const SIMULATE_NAV: NavItem[] = [
  {
    id: "sandbox",
    label: "안전 가상 실행 (샌드박스)",
    icon: <Beaker size={18} />,
    description: "테스트 케이스 자동 + 격리 실행",
    tooltip: "단계 하나를 골라 테스트 케이스 100건을 자동 생성하고, 격리된 안전한 환경(샌드박스)에서 파이썬으로 실제 실행. 자바 코드의 어느 라인이 실행됐는지 색칠해서 보여줍니다.",
  },
  {
    id: "scenarios",
    label: "시나리오 라이브러리",
    icon: <BookMarked size={18} />,
    description: "미리 준비된 룰 변경 카탈로그",
    tooltip: "이미 준비된 룰 변경 8건 (실수율 0.92 / EDGING 와일드카드 누락 / PlantMapping 변경 등). \"실행\" 클릭 한 번으로 잡 큐에 등록.",
  },
];

const GOVERN_NAV: NavItem[] = [
  {
    id: "history",
    label: "실행 이력",
    icon: <History size={18} />,
    description: "모든 실행 기록 + 기준 결과",
    tooltip: "지난 모든 실행 기록 (4초마다 갱신). 어느 결과를 \"기준 결과\"로 저장할지 여기서 정합니다. 기준 결과를 저장해 두면 같은 시나리오 재실행 시 자동으로 차이를 비교해 줍니다.",
  },
  {
    id: "regression",
    label: "재실행 비교 (차이 검증)",
    icon: <GitCompare size={18} />,
    description: "기준 결과 ↔ 새 실행 차이",
    tooltip: "기준 결과와 새로 실행한 결과의 모든 출력 필드를 하나하나 비교. 변경된 값이 0건 = 수정해도 기존 결과를 안 깨뜨림(안전).",
  },
  {
    id: "impact",
    label: "변경 영향 분석",
    icon: <Flame size={18} />,
    description: "변경 전·후 결과 분포",
    tooltip: "변경 전·후로 같은 표본을 실행하고 결과 분포를 겹쳐 보여줍니다. \"통과 → 실패\" 흐름 다이어그램 (Cascade Sankey) + 히스토그램 비교.",
  },
  {
    id: "differential",
    label: "Java ↔ Python 비교",
    icon: <GitCompare size={18} />,
    description: "양쪽 동시 실행 + 결과 차이",
    tooltip: "같은 입력으로 자바 SdDesigner.design() 와 파이썬 pipeline_full 양쪽 실행 → 필드별 결과 차이 (BigDecimal tolerance 적용). transpile 정확도 검증의 ground truth.",
  },
];

const NAVIGATE_NAV: NavItem[] = [
  {
    id: "bridge",
    label: "온톨로지 브릿지",
    icon: <Link2 size={18} />,
    description: "용어 → 추천 시나리오",
    tooltip: "도메인 용어 (실수율 / 두께 / EDGING / PlantMapping …) 를 검색하면 → 영향받는 단계 + 추천 시나리오 자동 도출. Section 2 의 온톨로지 그래프와 결합.",
  },
  {
    id: "navigator",
    label: "코드 내비게이터",
    icon: <Compass size={18} />,
    description: "용어 → 자바 코드 위치",
    tooltip: "비즈니스 용어를 자바 코드 라인 위치로 매핑 (코드 미리보기). \"여기서 시뮬\" 버튼으로 샌드박스에 바로 넘김.",
  },
];

const ONBOARDING_STEPS = [
  {
    id: "intro",
    title: "환영합니다 — Section 3 코드 기반 온톨로지 시뮬레이션",
    body: "자바 시스템 (slab-design 21단계 알고리즘) 을 안 돌리고도, 룰 한 줄 변경 결과를 파이썬으로 실제 실행해서 보여주는 플랫폼입니다. 자바 코드에서 추출한 도메인 그래프(온톨로지) 가 어떤 시나리오를 돌릴지 안내합니다. 5분 투어로 핵심 메뉴를 안내합니다.",
    cta: { label: "홈에서 배경 보기", targetView: "home" },
  },
  {
    id: "scenarios",
    title: "1단계 — 시나리오 라이브러리에서 시작",
    body: "이미 준비된 \"실수율 0.95 → 0.92\" 같은 시나리오를 클릭 한 번으로 실행해 보세요. YAML 직접 작성하지 않아도 됩니다.",
    cta: { label: "시나리오 가기", targetView: "scenarios" },
  },
  {
    id: "history",
    title: "2단계 — 실행 이력 + 기준 결과 저장",
    body: "이번 실행 결과를 \"기준 결과(baseline)\" 로 저장해 두면, 나중에 같은 시나리오를 다시 돌릴 때 시스템이 자동으로 \"기준이랑 뭐가 달라졌는지\" 비교해서 보여줍니다. 룰 수정 후 기존 결과를 깨지 않았는지 확인할 때 사용합니다.",
    cta: { label: "이력 보기", targetView: "history" },
  },
  {
    id: "sandbox",
    title: "3단계 — 안전 가상 실행에서 직접 돌리기",
    body: "단계 하나를 고르면 테스트 케이스 100건이 자동으로 만들어지고, 격리된 안전한 환경에서 파이썬으로 실제 실행됩니다. 결과는 자바 코드의 어느 라인이 실행됐는지 색칠로 보여줘요 (빨강 = 어떤 케이스로도 도달 못 한 위험 분기).",
    cta: { label: "샌드박스 가기", targetView: "sandbox" },
  },
  {
    id: "bridge",
    title: "4단계 — 도메인 용어로 추천 받기",
    body: "어떤 시나리오를 만들지 막막하면, 온톨로지 브릿지에 \"실수율\" 같은 용어를 검색하세요. 영향받는 단계 + 추천 입력값이 자동으로 채워집니다. 자연어로 \"HR 실수율 0.85로 줄이면?\" 식으로 물어볼 수도 있어요 (AI 어시스턴트).",
    cta: { label: "브릿지 가기", targetView: "bridge" },
  },
];

const VALID_VIEWS: SimView[] = [
  "home", "sandbox", "scenarios", "history",
  "regression", "impact", "navigator", "bridge", "differential",
];

function readInitialView(): SimView {
  if (typeof window === "undefined") return "home";
  const params = new URLSearchParams(window.location.search);
  const v = params.get("view");
  if (v && (VALID_VIEWS as string[]).includes(v)) return v as SimView;
  return "home";
}

export function SimulationSection() {
  const [active, setActive] = useState<SimView>(readInitialView);
  const [handoffStepId, setHandoffStepId] = useState<string | null>(null);

  useEffect(() => {
    const onPop = () => setActive(readInitialView());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const handoffToSandbox = (stepId: string) => {
    setHandoffStepId(stepId);
    setActive("sandbox");
  };

  const handoffFromBridge = (stepId: string, _presetInputs: Record<string, unknown>) => {
    setHandoffStepId(stepId);
    setActive("sandbox");
  };

  function renderNavButton(item: NavItem) {
    const isActive = active === item.id;
    return (
      <button
        key={item.id}
        onClick={() => setActive(item.id)}
        title={item.tooltip}
        className={`flex items-start gap-2 px-3 py-2 rounded text-sm transition-colors text-left ${
          isActive
            ? "bg-primary/10 text-primary font-medium"
            : "text-muted-foreground hover:bg-muted hover:text-foreground"
        }`}
      >
        <span className="mt-0.5">{item.icon}</span>
        <span className="flex-1 min-w-0">
          <span className="block">{item.label}</span>
          <span className="block text-[10px] text-muted-foreground/70 font-normal mt-0.5 truncate">
            {item.description}
          </span>
        </span>
      </button>
    );
  }

  function renderNavGroup(title: string, items: NavItem[]) {
    return (
      <>
        <div className="flex items-center gap-2 px-3 py-2 mt-2 first:mt-0">
          <Settings2 className="h-3 w-3 text-muted-foreground/60" />
          <span className="text-[10px] font-medium text-muted-foreground/60 uppercase tracking-wider">
            {title}
          </span>
          <div className="flex-1 h-px bg-border" />
        </div>
        {items.map(renderNavButton)}
      </>
    );
  }

  return (
    <div className="flex h-full">
      {/* Left nav */}
      <div className="w-56 border-r border-border bg-muted/30 p-3 flex flex-col gap-1 overflow-y-auto">
        <div className="px-2 py-3 mb-2">
          <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <Zap size={16} className="text-primary" />
            시뮬레이션
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            코드 기반 온톨로지 시뮬레이션
          </p>
        </div>

        {HOME_NAV.map(renderNavButton)}
        {renderNavGroup("실행", SIMULATE_NAV)}
        {renderNavGroup("운영", GOVERN_NAV)}
        {renderNavGroup("탐색", NAVIGATE_NAV)}

        <div className="mt-auto mx-2 px-2 py-2 rounded bg-primary/5 border border-primary/20">
          <p className="text-[10px] text-primary/80 font-medium">대상 코드베이스</p>
          <p className="text-[10px] text-muted-foreground mt-0.5 font-mono truncate">
            sample-repos/slab-design
          </p>
        </div>
      </div>

      {/* Main */}
      <div className="flex-1 overflow-auto">
        <div className="p-6">
          {active !== "home" && (
            <OnboardingBanner
              steps={ONBOARDING_STEPS}
              onJump={(v) => setActive(v as SimView)}
            />
          )}

          {active === "home" && <HomeDashboardPanel onJump={(v) => setActive(v as SimView)} />}
          {active === "sandbox" && (
            <SandboxPanel
              initialStepId={handoffStepId ?? undefined}
              onConsumeInitial={() => setHandoffStepId(null)}
            />
          )}
          {active === "scenarios" && <ScenarioLibraryPanel />}
          {active === "history" && <RunHistoryPanel />}
          {active === "regression" && <RegressionPanel />}
          {active === "impact" && <ImpactPanel />}
          {active === "navigator" && <NavigatorPanel onHandoffToSandbox={handoffToSandbox} />}
          {active === "differential" && <JavaPythonComparePanel />}
          {active === "bridge" && (
            <OntologyBridgePanel onHandoffToSandbox={handoffFromBridge} />
          )}
        </div>
      </div>
    </div>
  );
}
