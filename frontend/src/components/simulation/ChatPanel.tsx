"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Square, ChevronDown, ChevronRight, Wrench } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useSimulationStore } from "@/lib/simulation/useSimulationStore";
import { SCENARIO_META } from "@/lib/simulation/types";
import { runSlabAgent } from "@/lib/simulation/api";
import { cn } from "@/lib/utils";
import type { SlabSizeParams } from "@/lib/simulation/types";

export function ChatPanel() {
  const {
    activeScenario,
    messages,
    isRunning,
    orders,
    lastAgentResult,
    slabs,
    setLastAgentResult,
    setPendingSlabParams,
    setActiveScenario,
    addUserMessage,
    startAssistantMessage,
    appendContent,
    addThinkingStep,
    addToolCall,
    finalizeMessage,
    setIsRunning,
    setAbortController,
    stopAgent,
    setSlabs,
    setGraphHighlight,
  } = useSimulationStore();

  const [input, setInput] = useState("");
  const [expandedThinking, setExpandedThinking] = useState<Set<string>>(new Set());
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const meta = SCENARIO_META[activeScenario];

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = useCallback(async () => {
    const text = input.trim();
    if (!text || isRunning) return;

    setInput("");
    addUserMessage(text);
    const assistantId = startAssistantMessage();

    const ac = new AbortController();
    setAbortController(ac);
    setIsRunning(true);

    try {
      await runSlabAgent(
        activeScenario,
        text,
        {
          onThinking: (message) => {
            addThinkingStep(assistantId, { message, timestamp: Date.now() });
          },
          onToolCall: (tool, args) => {
            addToolCall(assistantId, { tool, args, timestamp: Date.now() });
          },
          onToolResult: (tool, result) => {
            // Update the last tool call with result
            useSimulationStore.setState((state) => ({
              messages: state.messages.map((m) => {
                if (m.id !== assistantId) return m;
                const calls = [...(m.tool_calls ?? [])];
                const idx = calls.findLastIndex((c) => c.tool === tool && !c.result);
                if (idx >= 0) calls[idx] = { ...calls[idx], result };
                return { ...m, tool_calls: calls };
              }),
            }));
          },
          onContentDelta: (delta) => {
            appendContent(assistantId, delta);
          },
          onSlabState: (slabs) => {
            setSlabs(slabs);
          },
          onGraphState: (state) => {
            setGraphHighlight(state);
          },
          onDone: (result) => {
            finalizeMessage(assistantId);
            setIsRunning(false);
            setAbortController(null);
            if (result && typeof result === "object") {
              setLastAgentResult(result as Record<string, unknown>);
            }
          },
          onError: (msg) => {
            appendContent(assistantId, `\n\n❌ 오류: ${msg}`);
            finalizeMessage(assistantId);
            setIsRunning(false);
            setAbortController(null);
          },
        },
        ac.signal
      );
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        appendContent(assistantId, `\n\n❌ 연결 오류: ${(err as Error).message}`);
      }
      finalizeMessage(assistantId);
      setIsRunning(false);
      setAbortController(null);
    }
  }, [
    input,
    isRunning,
    activeScenario,
    addUserMessage,
    startAssistantMessage,
    appendContent,
    addThinkingStep,
    addToolCall,
    finalizeMessage,
    setIsRunning,
    setAbortController,
    setSlabs,
    setGraphHighlight,
  ]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const useExample = () => {
    setInput(meta.example_prompt);
    textareaRef.current?.focus();
  };

  const toggleThinking = (msgId: string) => {
    setExpandedThinking((prev) => {
      const next = new Set(prev);
      if (next.has(msgId)) next.delete(msgId);
      else next.add(msgId);
      return next;
    });
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-auto p-3 space-y-3">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center py-8">
            <div
              className="w-12 h-12 rounded-full flex items-center justify-center text-2xl mb-3"
              style={{ backgroundColor: meta.color + "22", border: `1px solid ${meta.color}44` }}
            >
              {meta.icon}
            </div>
            <p className="text-sm font-medium">{meta.title}</p>
            <p className="text-xs text-muted-foreground mt-1 max-w-xs">{meta.description}</p>
            <button
              onClick={useExample}
              className="mt-4 text-xs px-3 py-1.5 rounded-md border hover:bg-muted transition-colors text-muted-foreground"
            >
              예시 질문 사용하기
            </button>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={cn("flex", msg.role === "user" ? "justify-end" : "justify-start")}>
            {msg.role === "user" ? (
              <div className="max-w-[85%] bg-primary text-primary-foreground px-3 py-2 rounded-xl rounded-tr-sm text-sm">
                {msg.content}
              </div>
            ) : (
              <div className="max-w-full w-full space-y-2">
                {/* Thinking steps */}
                {(msg.thinking_steps?.length ?? 0) > 0 && (
                  <div className="border rounded-lg overflow-hidden">
                    <button
                      onClick={() => toggleThinking(msg.id)}
                      className="w-full flex items-center justify-between px-3 py-1.5 text-xs text-muted-foreground bg-muted/50 hover:bg-muted transition-colors"
                    >
                      <span className="flex items-center gap-1.5">
                        <span className="animate-pulse">🤔</span>
                        추론 과정 ({msg.thinking_steps?.length ?? 0}단계)
                        {msg.isStreaming && (
                          <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                        )}
                      </span>
                      {expandedThinking.has(msg.id) ? (
                        <ChevronDown className="w-3 h-3" />
                      ) : (
                        <ChevronRight className="w-3 h-3" />
                      )}
                    </button>
                    {expandedThinking.has(msg.id) && (
                      <div className="px-3 py-2 space-y-1 bg-muted/20">
                        {msg.thinking_steps?.map((step, i) => (
                          <div key={i} className="flex items-start gap-1.5 text-xs text-muted-foreground">
                            <span className="mt-0.5 text-blue-400 shrink-0">→</span>
                            <span>{step.message}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Tool calls */}
                {(msg.tool_calls?.length ?? 0) > 0 && (
                  <div className="space-y-1">
                    {msg.tool_calls?.map((call, i) => (
                      <div key={i} className="border border-dashed rounded-md px-2.5 py-1.5 text-xs">
                        <div className="flex items-center gap-1.5 text-muted-foreground">
                          <Wrench className="w-3 h-3" />
                          <code className="text-blue-400 font-mono">{call.tool}</code>
                          {call.result !== undefined ? (
                            <span className="text-green-500 ml-auto">✓</span>
                          ) : (
                            <span className="ml-auto animate-spin text-yellow-400">⟳</span>
                          )}
                        </div>
                        <div className="mt-1 text-muted-foreground/70 font-mono text-[10px] truncate">
                          {JSON.stringify(call.args).slice(0, 80)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Main content */}
                {msg.content && (
                  <div className="prose prose-sm dark:prose-invert max-w-none text-sm">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        table: ({ ...props }) => (
                          <div className="overflow-x-auto">
                            <table className="text-xs border-collapse" {...props} />
                          </div>
                        ),
                        th: ({ ...props }) => (
                          <th className="border px-2 py-1 bg-muted font-medium text-left" {...props} />
                        ),
                        td: ({ ...props }) => (
                          <td className="border px-2 py-1" {...props} />
                        ),
                        code: ({ children, ...props }) => (
                          <code className="bg-muted px-1 py-0.5 rounded text-xs font-mono" {...props}>
                            {children}
                          </code>
                        ),
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                    {msg.isStreaming && (
                      <span className="inline-block w-1.5 h-4 bg-foreground/60 animate-pulse ml-0.5 align-middle" />
                    )}
                  </div>
                )}

                {/* Loading indicator */}
                {msg.isStreaming && !msg.content && (
                  <div className="flex gap-1 px-1">
                    {[0, 1, 2].map((i) => (
                      <div
                        key={i}
                        className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce"
                        style={{ animationDelay: `${i * 0.15}s` }}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* 에이전트 완료 후 Slab 설계 3D 뷰어 연결 버튼 */}
      {!isRunning && (() => {
        const orderId = lastAgentResult?.order_id as string | undefined;
        const order = orderId ? orders.find((o) => o.order_id === orderId) : undefined;

        // Scenario A: 조정된 폭으로 3D 슬랩 설계 확인
        if (activeScenario === "A" && lastAgentResult?.suggested_width) {
          const suggestedWidth = lastAgentResult.suggested_width as number;
          return (
            <div className="px-3 pb-2">
              <button
                onClick={() => {
                  const baseParams: SlabSizeParams = {
                    target_width: suggestedWidth,
                    thickness: 250,
                    target_length: (order?.target_length ?? 11700),
                    unit_weight: order?.slab_weight ?? Math.round(((order?.order_weight_min ?? 18000) + (order?.order_weight_max ?? 24000)) / 2),
                    split_count: order?.split_count ?? 2,
                    yield_rate: order?.yield_rate ?? 0.943,
                    assigned_rolling: order?.assigned_rolling ?? "HR-A",
                    assigned_caster: order?.assigned_caster ?? "CC-01",
                  };
                  setPendingSlabParams(baseParams);
                  setActiveScenario("SLAB_DESIGN");
                }}
                className="w-full text-xs py-2 px-3 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors flex items-center justify-center gap-1.5"
              >
                🧊 이 주문을 Slab 설계 3D로 확인
                <span className="text-indigo-200 text-[10px]">
                  (조정 폭 {suggestedWidth.toLocaleString()}mm)
                </span>
              </button>
            </div>
          );
        }

        // Scenario B: 영향받은 슬랩을 3D 설계로 확인
        if (activeScenario === "B" && slabs.length > 0) {
          const firstSlab = slabs[0];
          return (
            <div className="px-3 pb-2">
              <button
                onClick={() => {
                  const params: SlabSizeParams = {
                    target_width: firstSlab.width,
                    thickness: firstSlab.thickness,
                    target_length: firstSlab.length,
                    unit_weight: order?.slab_weight ?? Math.round(((order?.order_weight_min ?? 16000) + (order?.order_weight_max ?? 24000)) / 2),
                    split_count: firstSlab.split_count ?? 2,
                    yield_rate: order?.yield_rate ?? 0.943,
                    assigned_rolling: order?.assigned_rolling ?? "HR-A",
                    assigned_caster: order?.assigned_caster ?? "CC-01",
                  };
                  setPendingSlabParams(params);
                  setActiveScenario("SLAB_DESIGN");
                }}
                className="w-full text-xs py-2 px-3 rounded-lg bg-amber-600 hover:bg-amber-500 text-white transition-colors flex items-center justify-center gap-1.5"
              >
                🧊 영향받은 슬랩 Slab 설계 3D로 확인
                <span className="text-amber-200 text-[10px]">
                  ({slabs.length}개 중 첫 번째 · {firstSlab.width.toLocaleString()}mm)
                </span>
              </button>
            </div>
          );
        }

        // Scenario C: 최적 분할수로 3D 설계 확인
        if (activeScenario === "C" && lastAgentResult?.recommended_split_count) {
          const recSplit = lastAgentResult.recommended_split_count as number;
          return (
            <div className="px-3 pb-2">
              <button
                onClick={() => {
                  const baseParams: SlabSizeParams = {
                    target_width: order?.target_width ?? 1040,
                    thickness: 250,
                    target_length: order?.target_length ?? 11700,
                    unit_weight: order?.slab_weight ?? Math.round(((order?.order_weight_min ?? 16000) + (order?.order_weight_max ?? 23000)) / 2),
                    split_count: recSplit,
                    yield_rate: order?.yield_rate ?? 0.943,
                    assigned_rolling: order?.assigned_rolling ?? "HR-A",
                    assigned_caster: order?.assigned_caster ?? "CC-01",
                  };
                  setPendingSlabParams(baseParams);
                  setActiveScenario("SLAB_DESIGN");
                }}
                className="w-full text-xs py-2 px-3 rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors flex items-center justify-center gap-1.5"
              >
                🧊 최적 분할수 {recSplit}개를 Slab 설계 3D로 확인
              </button>
            </div>
          );
        }

        return null;
      })()}

      {/* Input */}
      <div className="border-t p-3">
        {messages.length > 0 && !isRunning && (
          <button
            onClick={useExample}
            className="w-full mb-2 text-xs text-muted-foreground hover:text-foreground transition-colors text-left px-1"
          >
            💡 {meta.example_prompt.slice(0, 60)}...
          </button>
        )}
        <div className="flex gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`시나리오 ${activeScenario}: ${meta.title}에 대해 질문하세요...`}
            className="flex-1 min-h-[60px] max-h-[120px] resize-none rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            disabled={isRunning}
          />
          <div className="flex flex-col gap-1.5">
            {isRunning ? (
              <button
                onClick={stopAgent}
                className="p-2 rounded-md bg-red-500 hover:bg-red-600 text-white transition-colors"
                title="중지"
              >
                <Square className="w-4 h-4" />
              </button>
            ) : (
              <button
                onClick={handleSubmit}
                disabled={!input.trim()}
                className="p-2 rounded-md bg-primary hover:bg-primary/90 text-primary-foreground disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                title="전송 (Enter)"
              >
                <Send className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
        <p className="text-[10px] text-muted-foreground mt-1.5">
          Enter로 전송 · Shift+Enter 줄바꿈
        </p>
      </div>
    </div>
  );
}
