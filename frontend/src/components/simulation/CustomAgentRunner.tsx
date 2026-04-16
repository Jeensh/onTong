"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Square, ChevronDown, ChevronRight, Wrench } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useSimulationStore } from "@/lib/simulation/useSimulationStore";
import { runCustomAgent } from "@/lib/simulation/api";
import { cn } from "@/lib/utils";

interface CustomAgentRunnerProps {
  agentId: string;
}

export function CustomAgentRunner({ agentId }: CustomAgentRunnerProps) {
  const {
    customAgents,
    customAgentMessages,
    customAgentRunning,
    addCustomAgentUserMessage,
    startCustomAgentAssistantMessage,
    appendCustomAgentContent,
    addCustomAgentThinkingStep,
    addCustomAgentToolCall,
    finalizeCustomAgentMessage,
    setCustomAgentRunning,
    setCustomAgentAbortController,
    stopCustomAgent,
    customAgentAbortControllers,
  } = useSimulationStore();

  const agent = customAgents.find((a) => a.id === agentId);
  const messages = customAgentMessages[agentId] ?? [];
  const isRunning = customAgentRunning[agentId] ?? false;

  const [input, setInput] = useState("");
  const [expandedThinking, setExpandedThinking] = useState<Set<string>>(new Set());
  const [expandedTools, setExpandedTools] = useState<Set<string>>(new Set());
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = useCallback(async () => {
    const text = input.trim();
    if (!text || isRunning || !agent) return;

    setInput("");
    addCustomAgentUserMessage(agentId, text);
    const assistantId = startCustomAgentAssistantMessage(agentId);

    const ac = new AbortController();
    setCustomAgentAbortController(agentId, ac);
    setCustomAgentRunning(agentId, true);

    try {
      await runCustomAgent(
        agentId,
        text,
        {
          onThinking: (message) => {
            addCustomAgentThinkingStep(agentId, assistantId, {
              message,
              timestamp: Date.now(),
            });
          },
          onToolCall: (tool, args) => {
            addCustomAgentToolCall(agentId, assistantId, {
              tool,
              args,
              timestamp: Date.now(),
            });
          },
          onToolResult: (tool, result) => {
            useSimulationStore.setState((state) => ({
              customAgentMessages: {
                ...state.customAgentMessages,
                [agentId]: (state.customAgentMessages[agentId] ?? []).map((m) => {
                  if (m.id !== assistantId) return m;
                  const calls = [...(m.tool_calls ?? [])];
                  const idx = calls.findLastIndex(
                    (c) => c.tool === tool && !c.result
                  );
                  if (idx >= 0) calls[idx] = { ...calls[idx], result };
                  return { ...m, tool_calls: calls };
                }),
              },
            }));
          },
          onContentDelta: (delta) => {
            appendCustomAgentContent(agentId, assistantId, delta);
          },
          onDone: () => {
            finalizeCustomAgentMessage(agentId, assistantId);
            setCustomAgentRunning(agentId, false);
            setCustomAgentAbortController(agentId, null);
          },
          onError: (msg) => {
            appendCustomAgentContent(agentId, assistantId, `\n\n❌ 오류: ${msg}`);
            finalizeCustomAgentMessage(agentId, assistantId);
            setCustomAgentRunning(agentId, false);
            setCustomAgentAbortController(agentId, null);
          },
        },
        ac.signal
      );
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        appendCustomAgentContent(
          agentId,
          assistantId,
          `\n\n❌ 연결 오류: ${(err as Error).message}`
        );
      }
      finalizeCustomAgentMessage(agentId, assistantId);
      setCustomAgentRunning(agentId, false);
      setCustomAgentAbortController(agentId, null);
    }
  }, [input, isRunning, agent, agentId]);

  const toggleThinking = (msgId: string) => {
    setExpandedThinking((prev) => {
      const next = new Set(prev);
      next.has(msgId) ? next.delete(msgId) : next.add(msgId);
      return next;
    });
  };

  const toggleTools = (msgId: string) => {
    setExpandedTools((prev) => {
      const next = new Set(prev);
      next.has(msgId) ? next.delete(msgId) : next.add(msgId);
      return next;
    });
  };

  if (!agent) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
        에이전트를 찾을 수 없습니다.
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* 헤더 */}
      <div
        className="flex items-center gap-3 px-4 py-2.5 border-b"
        style={{ backgroundColor: agent.color + "15" }}
      >
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center text-lg shrink-0"
          style={{ backgroundColor: agent.color + "30" }}
        >
          {agent.icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold truncate">{agent.name}</div>
          <div className="text-xs text-muted-foreground truncate">
            {agent.description}
          </div>
        </div>
        {isRunning && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span
              className="w-2 h-2 rounded-full animate-pulse"
              style={{ backgroundColor: agent.color }}
            />
            실행 중
          </div>
        )}
      </div>

      {/* 메시지 영역 */}
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {/* 초기 안내 */}
        {messages.length === 0 && (
          <div className="flex justify-start">
            <div className="max-w-[85%] p-3 rounded-xl rounded-tl-sm bg-muted text-sm">
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {`**${agent.icon} ${agent.name}** 에이전트입니다.\n\n${agent.description}\n\n${
                    agent.example_prompt
                      ? `**예시 질문:**\n> ${agent.example_prompt}`
                      : "무엇이 궁금하신가요?"
                  }`}
                </ReactMarkdown>
              </div>
            </div>
          </div>
        )}

        {/* 대화 메시지 */}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cn(
              "flex",
              msg.role === "user" ? "justify-end" : "justify-start"
            )}
          >
            {msg.role === "user" ? (
              <div
                className="max-w-[85%] px-3 py-2 rounded-xl rounded-tr-sm text-sm text-white"
                style={{ backgroundColor: agent.color }}
              >
                {msg.content}
              </div>
            ) : (
              <div className="max-w-[85%] space-y-2">
                {/* Thinking steps */}
                {(msg.thinking_steps?.length ?? 0) > 0 && (
                  <div>
                    <button
                      onClick={() => toggleThinking(msg.id)}
                      className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors px-1"
                    >
                      {expandedThinking.has(msg.id) ? (
                        <ChevronDown className="w-3 h-3" />
                      ) : (
                        <ChevronRight className="w-3 h-3" />
                      )}
                      <span>
                        🤔 추론 {msg.thinking_steps!.length}단계
                        {msg.isStreaming && (
                          <span className="ml-1 animate-pulse">...</span>
                        )}
                      </span>
                    </button>
                    {expandedThinking.has(msg.id) && (
                      <div className="mt-1 ml-2 pl-2 border-l-2 border-muted space-y-0.5">
                        {msg.thinking_steps!.map((step, i) => (
                          <div key={i} className="text-xs text-muted-foreground">
                            {step.message}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Tool calls */}
                {(msg.tool_calls?.length ?? 0) > 0 && (
                  <div>
                    <button
                      onClick={() => toggleTools(msg.id)}
                      className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors px-1"
                    >
                      {expandedTools.has(msg.id) ? (
                        <ChevronDown className="w-3 h-3" />
                      ) : (
                        <ChevronRight className="w-3 h-3" />
                      )}
                      <Wrench className="w-3 h-3" />
                      <span>도구 호출 {msg.tool_calls!.length}건</span>
                    </button>
                    {expandedTools.has(msg.id) && (
                      <div className="mt-1 space-y-1">
                        {msg.tool_calls!.map((call, i) => (
                          <div
                            key={i}
                            className="ml-2 p-2 rounded-lg bg-muted/50 text-xs border"
                          >
                            <div className="font-mono font-medium text-blue-600 dark:text-blue-400">
                              {call.tool}(
                              {Object.entries(call.args)
                                .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
                                .join(", ")}
                              )
                            </div>
                            {call.result !== undefined && (
                              <div className="mt-1 text-muted-foreground line-clamp-3">
                                → {JSON.stringify(call.result)}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Content */}
                {msg.content && (
                  <div className="bg-muted p-3 rounded-xl rounded-tl-sm">
                    <div className="prose prose-sm dark:prose-invert max-w-none text-sm">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.content}
                      </ReactMarkdown>
                      {msg.isStreaming && (
                        <span className="inline-block w-1.5 h-4 bg-foreground/60 animate-pulse ml-0.5 align-middle" />
                      )}
                    </div>
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

      {/* 입력창 */}
      <div className="border-t p-3">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
            placeholder={
              agent.example_prompt
                ? `예: ${agent.example_prompt.slice(0, 50)}...`
                : "질문을 입력하세요..."
            }
            className="flex-1 min-h-[60px] max-h-[120px] resize-none rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            disabled={isRunning}
          />
          <div className="flex flex-col gap-1.5">
            {isRunning ? (
              <button
                onClick={() => stopCustomAgent(agentId)}
                className="p-2 rounded-md bg-red-500 hover:bg-red-600 text-white transition-colors"
                title="중지"
              >
                <Square className="w-4 h-4" />
              </button>
            ) : (
              <button
                onClick={handleSubmit}
                disabled={!input.trim()}
                className="p-2 rounded-md text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                style={{ backgroundColor: agent.color }}
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
