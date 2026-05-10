package com.example.slabdesign.feature.sd.trace;

/**
 * sd · trace · per-step execution outcome.
 *
 * OK    — action succeeded.
 * RETRY — A-a 루프 내부 분할수 fallback (DG108 catch → 다음 split 시도).
 * FAIL  — AlgorithmException 발생, 알고리즘 종결.
 * SKIP  — 사양상 미실행 (e.g. step 14 max-wgt mode 미구현).
 */
public enum TraceStatus {
    OK,
    RETRY,
    FAIL,
    SKIP
}
