/**
 * SSE client using fetch + ReadableStream.
 * Parses Server-Sent Events from the /api/agent/chat endpoint.
 */

export interface ThinkingStep {
  step: string;
  status: "start" | "done";
  label: string;
  detail: string;
}

export interface SSECallbacks {
  onRouting?: (data: { agent: string; confidence: number }) => void;
  onThinkingStep?: (data: ThinkingStep) => void;
  onContentDelta?: (delta: string) => void;
  onSources?: (sources: { doc: string; relevance: number; updated?: string; updated_by?: string; status?: string }[]) => void;
  onApprovalRequest?: (data: {
    action_id: string;
    action_type: string;
    path: string;
    diff_preview: string;
    content: string;
    original_content: string;
  }) => void;
  onConflictWarning?: (data: {
    details: string;
    conflicting_docs: string[];
    conflict_pairs?: { file_a: string; file_b: string; similarity: number; summary: string }[];
  }) => void;
  onError?: (data: {
    error_code: string;
    message: string;
    retry_hint: string | null;
  }) => void;
  onSkillMatch?: (data: {
    skill_path: string;
    skill_title: string;
    skill_icon: string;
    confidence: number;
  }) => void;
  onDone?: (data: { usage: { input_tokens: number; output_tokens: number } | null }) => void;
}

export async function streamChat(
  message: string,
  sessionId: string,
  callbacks: SSECallbacks,
  signal?: AbortSignal,
  attachedFiles?: string[],
  skillPath?: string
): Promise<void> {
  // SSE streams must bypass the Next.js rewrite proxy, which buffers
  // chunked responses and delays thinking_step events. Hit the backend directly.
  const backendUrl =
    typeof window !== "undefined" && window.location.hostname === "localhost"
      ? "http://localhost:8001"
      : "";

  const body: Record<string, unknown> = { message, session_id: sessionId };
  if (attachedFiles && attachedFiles.length > 0) {
    body.attached_files = attachedFiles;
  }
  if (skillPath) {
    body.skill_path = skillPath;
  }

  const res = await fetch(`${backendUrl}/api/agent/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok) {
    callbacks.onError?.({
      error_code: "HTTP_ERROR",
      message: `서버 오류: ${res.status}`,
      retry_hint: "서버 상태를 확인해주세요.",
    });
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) return;

  const decoder = new TextDecoder();
  let buffer = "";

  let currentEvent = "";
  let currentData = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE messages are separated by double newline (\n\n).
      // Process all complete messages; keep the trailing incomplete chunk in buffer.
      let boundary: number;
      while ((boundary = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);

        for (const line of block.split("\n")) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            currentData = line.slice(6);
          }
          // Ignore other lines (comments, empty, unknown fields)
        }

        if (currentEvent && currentData) {
          try {
            const parsed = JSON.parse(currentData);
            dispatchEvent(currentEvent, parsed, callbacks);
          } catch {
            // Non-JSON data, ignore
          }
        }
        currentEvent = "";
        currentData = "";
      }
    }
  } finally {
    reader.releaseLock();
  }
}

function dispatchEvent(
  event: string,
  data: Record<string, unknown>,
  callbacks: SSECallbacks
): void {
  switch (event) {
    case "routing":
      callbacks.onRouting?.(data as { agent: string; confidence: number });
      break;
    case "thinking_step":
      callbacks.onThinkingStep?.(data as unknown as ThinkingStep);
      break;
    case "content_delta":
      callbacks.onContentDelta?.(data.delta as string);
      break;
    case "sources":
      callbacks.onSources?.(
        data.sources as { doc: string; relevance: number; updated?: string; updated_by?: string; status?: string }[]
      );
      break;
    case "conflict_warning":
      callbacks.onConflictWarning?.(
        data as { details: string; conflicting_docs: string[]; conflict_pairs?: { file_a: string; file_b: string; similarity: number; summary: string }[] }
      );
      break;
    case "approval_request":
      callbacks.onApprovalRequest?.(
        data as {
          action_id: string;
          action_type: string;
          path: string;
          diff_preview: string;
          content: string;
          original_content: string;
        }
      );
      break;
    case "skill_match":
      callbacks.onSkillMatch?.(
        data as { skill_path: string; skill_title: string; skill_icon: string; confidence: number }
      );
      break;
    case "error":
      callbacks.onError?.(
        data as { error_code: string; message: string; retry_hint: string | null }
      );
      break;
    case "done":
      callbacks.onDone?.(
        data as { usage: { input_tokens: number; output_tokens: number } | null }
      );
      break;
  }
}
