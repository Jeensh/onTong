"use client";

import { useState } from "react";
import { Check } from "lucide-react";
import { useSimulationStore } from "@/lib/simulation/useSimulationStore";
import { createCustomAgent } from "@/lib/simulation/api";
import { SLAB_TOOLS } from "@/lib/simulation/types";
import { cn } from "@/lib/utils";

const PRESET_ICONS = ["🤖", "🔍", "📊", "⚙️", "🧮", "🏭", "📋", "🔧", "📐", "⚡"];
const PRESET_COLORS = [
  "#6366f1", "#ef4444", "#f59e0b", "#10b981",
  "#3b82f6", "#8b5cf6", "#ec4899", "#14b8a6",
];

export function CustomAgentFormBuilder() {
  const { addCustomAgent, setActiveView } = useSimulationStore();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [selectedTools, setSelectedTools] = useState<string[]>([]);
  const [examplePrompt, setExamplePrompt] = useState("");
  const [icon, setIcon] = useState("🤖");
  const [color, setColor] = useState("#6366f1");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleTool = (toolId: string) => {
    setSelectedTools((prev) =>
      prev.includes(toolId) ? prev.filter((t) => t !== toolId) : [...prev, toolId]
    );
  };

  const handleSubmit = async () => {
    if (!name.trim() || !description.trim() || !systemPrompt.trim()) {
      setError("이름, 설명, 시스템 프롬프트는 필수입니다.");
      return;
    }
    if (selectedTools.length === 0) {
      setError("사용할 도구를 하나 이상 선택해주세요.");
      return;
    }

    setError(null);
    setSubmitting(true);
    try {
      const newAgent = await createCustomAgent({
        name: name.trim(),
        description: description.trim(),
        icon,
        color,
        system_prompt: systemPrompt.trim(),
        available_tools: selectedTools,
        example_prompt: examplePrompt.trim(),
        created_by: "form",
      });
      addCustomAgent(newAgent);
      setActiveView({ kind: "custom_agent", agentId: newAgent.id });
    } catch (err) {
      setError(`등록 실패: ${(err as Error).message}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col h-full overflow-auto">
      {/* 헤더 */}
      <div className="flex items-center gap-2 px-6 py-3 border-b bg-muted/20 shrink-0">
        <span className="text-sm">📋</span>
        <span className="text-sm font-semibold">양식으로 Agent 만들기</span>
      </div>

      {/* 폼 */}
      <div className="flex-1 overflow-auto p-6 space-y-6 max-w-2xl mx-auto w-full">

        {/* 아이콘 + 색상 */}
        <div className="flex gap-6">
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">아이콘</label>
            <div className="flex flex-wrap gap-1.5">
              {PRESET_ICONS.map((ic) => (
                <button
                  key={ic}
                  onClick={() => setIcon(ic)}
                  className={cn(
                    "w-9 h-9 rounded-lg text-lg border-2 transition-all",
                    icon === ic
                      ? "border-primary bg-primary/10 scale-110"
                      : "border-transparent hover:border-muted-foreground/30"
                  )}
                >
                  {ic}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">색상</label>
            <div className="flex flex-wrap gap-1.5">
              {PRESET_COLORS.map((c) => (
                <button
                  key={c}
                  onClick={() => setColor(c)}
                  className={cn(
                    "w-7 h-7 rounded-full border-2 transition-all",
                    color === c ? "border-foreground scale-110" : "border-transparent"
                  )}
                  style={{ backgroundColor: c }}
                />
              ))}
            </div>
          </div>

          {/* 미리보기 */}
          <div className="flex flex-col items-center gap-1">
            <label className="text-xs font-medium text-muted-foreground">미리보기</label>
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl border"
              style={{ backgroundColor: color + "22", borderColor: color + "44" }}
            >
              {icon}
            </div>
          </div>
        </div>

        {/* 이름 */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold">
            에이전트 이름 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="예: DG320 자동 진단 에이전트"
            className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>

        {/* 설명 */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold">
            설명 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="이 에이전트가 무엇을 하는지 한 문장으로 설명하세요"
            className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>

        {/* 사용 도구 */}
        <div className="space-y-2">
          <label className="text-xs font-semibold">
            사용 도구 <span className="text-red-500">*</span>
          </label>
          <div className="grid grid-cols-2 gap-2">
            {SLAB_TOOLS.map((tool) => {
              const selected = selectedTools.includes(tool.id);
              return (
                <button
                  key={tool.id}
                  onClick={() => toggleTool(tool.id)}
                  className={cn(
                    "flex items-center gap-2 px-3 py-2.5 rounded-lg border text-xs text-left transition-all",
                    selected
                      ? "border-primary bg-primary/5 text-foreground"
                      : "border-border hover:border-muted-foreground/50 text-muted-foreground"
                  )}
                >
                  <div
                    className={cn(
                      "w-4 h-4 rounded border-2 flex items-center justify-center shrink-0",
                      selected ? "border-primary bg-primary" : "border-muted-foreground/40"
                    )}
                  >
                    {selected && <Check className="w-2.5 h-2.5 text-white" />}
                  </div>
                  <span>{tool.icon}</span>
                  <div>
                    <div className="font-medium text-[11px]">{tool.label}</div>
                    <div className="font-mono text-[9px] text-muted-foreground">{tool.id}</div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* 시스템 프롬프트 */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold">
            시스템 프롬프트 <span className="text-red-500">*</span>
          </label>
          <p className="text-[11px] text-muted-foreground">
            이 에이전트의 역할과 행동 방식을 상세히 정의하세요.
          </p>
          <textarea
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            placeholder={`예:\n당신은 POSCO Slab 설계 전문가입니다.\nDG320 에러가 발생한 주문을 진단하고, 자동으로 폭을 조정하여 해결 방안을 제시합니다.\n항상 주문 정보를 먼저 조회하고, 구체적인 수치와 함께 설명하세요.`}
            rows={6}
            className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-1 focus:ring-ring resize-none"
          />
        </div>

        {/* 예시 질문 */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold">예시 질문 (선택)</label>
          <input
            type="text"
            value={examplePrompt}
            onChange={(e) => setExamplePrompt(e.target.value)}
            placeholder="예: 주문 ORD-2024-0042의 DG320 에러를 분석해줘"
            className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>

        {/* 오류 메시지 */}
        {error && (
          <div className="px-3 py-2 rounded-md bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm border border-red-200 dark:border-red-800">
            {error}
          </div>
        )}

        {/* 등록 버튼 */}
        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="w-full py-2.5 px-4 rounded-lg text-sm font-medium text-white bg-primary hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {submitting ? "등록 중..." : `${icon} Agent 등록하기`}
        </button>
      </div>
    </div>
  );
}
