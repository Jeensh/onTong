"use client";

import { useState, useEffect } from "react";
import { BarChart3, Play, Loader2 } from "lucide-react";

interface ScenarioInfo {
  scenario_type: string;
  name: string;
  description: string;
  supported_outputs: string[];
}

export function SimulationSection() {
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/simulation/scenarios")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        setScenarios(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return (
    <div className="flex h-full">
      {/* Left: Scenario list */}
      <div className="w-72 border-r flex flex-col">
        <div className="p-3 border-b">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <BarChart3 className="w-4 h-4" />
            시뮬레이션 시나리오
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            시나리오를 선택하여 실행하세요
          </p>
        </div>
        <div className="flex-1 overflow-auto p-2">
          {loading && (
            <div className="flex items-center justify-center py-8 text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
              <span className="text-sm">로딩 중...</span>
            </div>
          )}
          {error && (
            <div className="p-3 text-sm text-red-600 bg-red-50 rounded">
              API 연결 실패: {error}
              <p className="text-xs mt-1 text-red-500">
                백엔드가 실행 중인지 확인하세요
              </p>
            </div>
          )}
          {scenarios.map((s) => (
            <button
              key={s.scenario_type}
              className="w-full text-left p-3 rounded-lg hover:bg-muted transition-colors mb-1"
            >
              <div className="text-sm font-medium">{s.name}</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                {s.description}
              </div>
              <div className="flex gap-1 mt-1.5">
                {s.supported_outputs.map((o) => (
                  <span
                    key={o}
                    className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground"
                  >
                    {o}
                  </span>
                ))}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Center: Dashboard area */}
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center max-w-md">
          <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mx-auto mb-4">
            <Play className="w-8 h-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-medium">시뮬레이션 대시보드</h3>
          <p className="text-sm text-muted-foreground mt-2">
            좌측에서 시나리오를 선택하면 이 영역에 파라미터 입력 폼과 결과 시각화가 표시됩니다.
          </p>
          <div className="mt-6 p-4 rounded-lg bg-muted/50 text-left">
            <p className="text-xs font-medium text-muted-foreground mb-2">개발 가이드</p>
            <ul className="text-xs text-muted-foreground space-y-1">
              <li>- 시나리오 목록은 <code className="bg-muted px-1 rounded">GET /api/simulation/scenarios</code>에서 가져옵니다</li>
              <li>- 실행은 <code className="bg-muted px-1 rounded">POST /api/simulation/scenario</code>를 호출합니다</li>
              <li>- 현재 Mock 모드로 동작하며 파라미터에 따라 동적 결과를 생성합니다</li>
              <li>- 이 영역에 ParameterForm + ScenarioDashboard를 구현하세요</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Right: Chat placeholder */}
      <div className="w-80 border-l flex flex-col">
        <div className="p-3 border-b">
          <h3 className="text-sm font-semibold">SimCopilot</h3>
          <p className="text-xs text-muted-foreground">시뮬레이션 AI 어시스턴트</p>
        </div>
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="text-center text-muted-foreground">
            <p className="text-sm">AI 어시스턴트가 여기에 표시됩니다</p>
            <p className="text-xs mt-1">
              시나리오 설계 도움, 결과 해석, 파라미터 추천 등
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
