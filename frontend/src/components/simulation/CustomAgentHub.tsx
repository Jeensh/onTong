"use client";

import { MessageSquare, FileText, Play, Trash2, Plus } from "lucide-react";
import { useSimulationStore } from "@/lib/simulation/useSimulationStore";
import { deleteCustomAgent as apiDeleteCustomAgent } from "@/lib/simulation/api";
import { SLAB_TOOLS } from "@/lib/simulation/types";

export function CustomAgentHub() {
  const { setActiveView, customAgents, deleteCustomAgent } = useSimulationStore();

  const handleDelete = async (id: string) => {
    try {
      await apiDeleteCustomAgent(id);
      deleteCustomAgent(id);
    } catch (err) {
      console.error("삭제 실패:", err);
    }
  };

  return (
    <div className="flex flex-col h-full overflow-auto p-6 bg-background">
      {/* 헤더 */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <span>🤖</span> Custom Agent
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Slab 설계 도메인에 특화된 나만의 AI 에이전트를 만들어 등록하세요.
          채팅 대화나 구조화된 양식으로 간편하게 생성할 수 있습니다.
        </p>
      </div>

      {/* 만들기 카드 */}
      <div className="grid grid-cols-2 gap-4 mb-8">
        <button
          onClick={() => setActiveView({ kind: "custom_chat_builder" })}
          className="flex flex-col items-start gap-3 p-5 rounded-xl border-2 border-dashed hover:border-primary hover:bg-primary/5 transition-all text-left group"
        >
          <div className="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center group-hover:scale-110 transition-transform">
            <MessageSquare className="w-5 h-5 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <div className="text-sm font-semibold">채팅으로 만들기</div>
            <div className="text-xs text-muted-foreground mt-0.5">
              AI와 자유롭게 대화하며 에이전트를 설계합니다. 원하는 것을 말하면 AI가 도와드립니다.
            </div>
          </div>
          <div className="flex items-center gap-1 text-xs text-primary font-medium">
            <Plus className="w-3 h-3" /> 시작하기
          </div>
        </button>

        <button
          onClick={() => setActiveView({ kind: "custom_form_builder" })}
          className="flex flex-col items-start gap-3 p-5 rounded-xl border-2 border-dashed hover:border-primary hover:bg-primary/5 transition-all text-left group"
        >
          <div className="w-10 h-10 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center group-hover:scale-110 transition-transform">
            <FileText className="w-5 h-5 text-purple-600 dark:text-purple-400" />
          </div>
          <div>
            <div className="text-sm font-semibold">양식으로 만들기</div>
            <div className="text-xs text-muted-foreground mt-0.5">
              구조화된 양식에 직접 입력하여 에이전트를 정밀하게 설정합니다.
            </div>
          </div>
          <div className="flex items-center gap-1 text-xs text-primary font-medium">
            <Plus className="w-3 h-3" /> 시작하기
          </div>
        </button>
      </div>

      {/* 사용 가능한 도구 소개 */}
      <div className="mb-8">
        <h3 className="text-sm font-semibold mb-3">사용 가능한 Slab 설계 도구</h3>
        <div className="grid grid-cols-2 gap-2">
          {SLAB_TOOLS.map((tool) => (
            <div key={tool.id} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-muted/50 text-xs">
              <span>{tool.icon}</span>
              <div>
                <div className="font-medium">{tool.label}</div>
                <div className="text-muted-foreground font-mono text-[10px]">{tool.id}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 등록된 에이전트 목록 */}
      {customAgents.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-3">
            등록된 Agent ({customAgents.length})
          </h3>
          <div className="space-y-3">
            {customAgents.map((agent) => (
              <div
                key={agent.id}
                className="flex items-start gap-3 p-4 rounded-xl border bg-card hover:shadow-sm transition-shadow"
              >
                {/* 아이콘 */}
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center text-xl shrink-0"
                  style={{ backgroundColor: agent.color + "22" }}
                >
                  {agent.icon}
                </div>

                {/* 정보 */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold truncate">{agent.name}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground shrink-0">
                      {agent.created_by === "chat" ? "채팅 생성" : "양식 생성"}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                    {agent.description}
                  </p>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {agent.available_tools.slice(0, 3).map((t) => {
                      const tool = SLAB_TOOLS.find((st) => st.id === t);
                      return (
                        <span
                          key={t}
                          className="text-[10px] px-1.5 py-0.5 rounded-full border bg-background"
                        >
                          {tool?.icon} {tool?.label ?? t}
                        </span>
                      );
                    })}
                    {agent.available_tools.length > 3 && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full border bg-background text-muted-foreground">
                        +{agent.available_tools.length - 3}개
                      </span>
                    )}
                  </div>
                </div>

                {/* 액션 버튼 */}
                <div className="flex flex-col gap-1.5 shrink-0">
                  <button
                    onClick={() => setActiveView({ kind: "custom_agent", agentId: agent.id })}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium text-white transition-colors"
                    style={{ backgroundColor: agent.color }}
                  >
                    <Play className="w-3 h-3" />
                    실행
                  </button>
                  <button
                    onClick={() => handleDelete(agent.id)}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-md text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors border"
                  >
                    <Trash2 className="w-3 h-3" />
                    삭제
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {customAgents.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
          <span className="text-4xl mb-3">🤖</span>
          <p className="text-sm">아직 등록된 Agent가 없습니다.</p>
          <p className="text-xs mt-1">위에서 새 Agent를 만들어보세요!</p>
        </div>
      )}
    </div>
  );
}
