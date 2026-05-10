package com.example.slabdesign.feature.sd.trace;

import java.util.Map;

/**
 * sd · trace · single step input/output snapshot.
 *
 * step       — 1 ~ 21 알고리즘 step 번호.
 * stepName   — action class simple name (e.g. "SdThicknessAction").
 * phase      — "ONE_SHOT" | "AA_LOOP" | "FINAL" | "SAVE".
 * iteration  — A-a 루프 분할수 (one-shot 은 1).
 * input      — action 호출 직전 주요 입력 snapshot (Map).
 * output     — action 호출 후 주요 출력 snapshot (FAIL/RETRY/SKIP 시 null).
 * status     — OK | RETRY | FAIL | SKIP.
 * errorCode  — FAIL 시 SdErrorCode 상수 (e.g. "DG104"). 그 외 null.
 * errorMessage — FAIL/RETRY 시 사람이 읽을 메시지.
 * elapsedMs  — wrap() 측정 실행 시간 (ms). RETRY/SKIP 은 0.
 */
public record StepTrace(
    int step,
    String stepName,
    String phase,
    int iteration,
    Map<String, Object> input,
    Map<String, Object> output,
    TraceStatus status,
    String errorCode,
    String errorMessage,
    double elapsedMs
) {}
