"use client";

/**
 * Phase 3+5 hook — multiturn session lifecycle.
 *
 * 외부 노출:
 *   - state: sessionId / decisions / status / errors
 *   - actions: start / respond / confirm / reset / loadSession
 *
 * server-push (SSE): sessionId 설정되면 EventSource 자동 구독.
 *   `/session/{sid}/stream` 의 snapshot event 가 도착하면 state.decisions 갱신.
 *   백엔드 SSE 가 30초 timeout 후 close → 자동 reconnect.
 *   session.status="done" 도달 시 done event 받고 자동 close.
 *
 * mutation 후 `apiGetSession()` refresh 도 병행 — SSE 가 1초 polling 이라
 * 더 빠른 first-paint 확보.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  confirmTurn as apiConfirm,
  getSession as apiGetSession,
  MultiturnError,
  respond as apiRespond,
  startSession as apiStart,
  type DecisionView,
  type SessionInfo,
} from "@/lib/section3/multiturn";

export interface MultiturnSessionState {
  sessionId: string | null;
  session: SessionInfo | null;
  decisions: DecisionView[];
  pending: boolean;
  error: { status: number; detail: string } | null;
  lastNextGateKind: string | null;
}

const INITIAL: MultiturnSessionState = {
  sessionId: null,
  session: null,
  decisions: [],
  pending: false,
  error: null,
  lastNextGateKind: null,
};

const SSE_BASE = "/api/section3/multiturn";

export function useMultiturnSession() {
  const [state, setState] = useState<MultiturnSessionState>(INITIAL);
  const esRef = useRef<EventSource | null>(null);

  const refresh = useCallback(async (sid: string) => {
    const replay = await apiGetSession(sid);
    setState((prev) => ({
      ...prev,
      sessionId: sid,
      session: replay.session,
      decisions: replay.decisions,
    }));
  }, []);

  // SSE subscribe — sessionId 변경 시 새 EventSource open, unmount/done 시 close
  useEffect(() => {
    if (!state.sessionId) return;
    if (state.session?.status === "done") {
      esRef.current?.close();
      esRef.current = null;
      return;
    }

    const url = `${SSE_BASE}/session/${encodeURIComponent(state.sessionId)}/stream`;
    const es = new EventSource(url);
    esRef.current = es;

    es.addEventListener("snapshot", (ev) => {
      try {
        const data = JSON.parse((ev as MessageEvent).data);
        setState((prev) => ({
          ...prev,
          session: prev.session ? {
            ...prev.session,
            status: data.status,
          } : prev.session,
          decisions: data.decisions,
        }));
      } catch (e) {
        console.warn("SSE snapshot parse fail", e);
      }
    });

    es.addEventListener("done", () => {
      es.close();
      esRef.current = null;
    });

    es.addEventListener("gone", () => {
      es.close();
      esRef.current = null;
    });

    es.onerror = () => {
      // EventSource 자동 reconnect — 백엔드가 30초 후 close 하면 자연스럽게 재연결
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [state.sessionId, state.session?.status]);

  const start = useCallback(
    async (user_query: string, repo_id: string) => {
      setState({ ...INITIAL, pending: true });
      try {
        const r = await apiStart(user_query, repo_id);
        await refresh(r.session_id);
        setState((prev) => ({ ...prev, pending: false }));
        return r.session_id;
      } catch (e) {
        setState((prev) => ({
          ...prev,
          pending: false,
          error: errToState(e),
        }));
        return null;
      }
    },
    [refresh],
  );

  const respond = useCallback(
    async (message: string) => {
      if (!state.sessionId) return;
      setState((prev) => ({ ...prev, pending: true, error: null }));
      try {
        await apiRespond(state.sessionId, message);
        await refresh(state.sessionId);
        setState((prev) => ({ ...prev, pending: false }));
      } catch (e) {
        setState((prev) => ({
          ...prev,
          pending: false,
          error: errToState(e),
        }));
      }
    },
    [state.sessionId, refresh],
  );

  const confirm = useCallback(
    async (
      turn_no: number,
      action: "confirm" | "modify" | "retry",
      user_response: Record<string, unknown>,
    ) => {
      if (!state.sessionId) return;
      setState((prev) => ({ ...prev, pending: true, error: null }));
      try {
        const r = await apiConfirm(state.sessionId, turn_no, action, user_response);
        await refresh(state.sessionId);
        setState((prev) => ({
          ...prev, pending: false, lastNextGateKind: r.next_gate_kind,
        }));
      } catch (e) {
        setState((prev) => ({
          ...prev,
          pending: false,
          error: errToState(e),
        }));
      }
    },
    [state.sessionId, refresh],
  );

  const reset = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    setState(INITIAL);
  }, []);

  /** 기존 sid 로드 — 히스토리 브라우저에서 진입할 때. */
  const loadSession = useCallback(
    async (sid: string) => {
      esRef.current?.close();
      esRef.current = null;
      setState({ ...INITIAL, pending: true });
      try {
        await refresh(sid);
        setState((prev) => ({ ...prev, pending: false }));
      } catch (e) {
        setState((prev) => ({
          ...prev,
          pending: false,
          error: errToState(e),
        }));
      }
    },
    [refresh],
  );

  return { state, start, respond, confirm, reset, loadSession };
}

function errToState(e: unknown): { status: number; detail: string } {
  if (e instanceof MultiturnError) {
    return { status: e.status, detail: e.detail };
  }
  return { status: 0, detail: e instanceof Error ? e.message : String(e) };
}
