package com.example.slabdesign.feature.sd.trace;

import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Supplier;

/**
 * sd · trace · per-step input/output snapshot collector.
 *
 * SdDesigner 가 nullable 로 주입받아 사용. null 이면 trace 비활성 (zero overhead path).
 * 단일 designer 호출 단위로 새 인스턴스 생성 — thread-safe 미보장.
 *
 * 사용:
 *   TraceCollector trace = new TraceCollector();
 *   designer.design(order, trace);
 *   List<StepTrace> steps = trace.traces();
 */
public class TraceCollector {

    private final List<StepTrace> traces = new ArrayList<>();

    /** 적재된 trace 의 불변 복사본. */
    public List<StepTrace> traces() {
        return List.copyOf(traces);
    }

    /**
     * action 실행을 wrap 하여 OK / FAIL trace 적재.
     * AlgorithmException 은 FAIL 로 기록 후 rethrow.
     * 그 외 RuntimeException 은 trace 미기록 — 기존 동작 보존.
     */
    @SuppressWarnings("unchecked")
    public <T> T wrap(int step, String stepName, String phase, int iteration,
                      Map<String, Object> input, Supplier<T> body) {
        long t0 = System.nanoTime();
        try {
            T result = body.get();
            double ms = (System.nanoTime() - t0) / 1_000_000.0;
            Map<String, Object> output;
            if (result == null) {
                output = Map.of();
            } else if (result instanceof Map<?, ?> m) {
                output = (Map<String, Object>) m;
            } else {
                output = Map.of("result", result);
            }
            traces.add(new StepTrace(step, stepName, phase, iteration, input, output,
                TraceStatus.OK, null, null, ms));
            return result;
        } catch (AlgorithmException e) {
            double ms = (System.nanoTime() - t0) / 1_000_000.0;
            traces.add(new StepTrace(step, stepName, phase, iteration, input, null,
                TraceStatus.FAIL, e.getErrorCode(), e.getMessage(), ms));
            throw e;
        }
    }

    /**
     * A-a 루프 내부 silent 분할수 fallback 시 호출 (DG108 catch 후).
     * status=RETRY · output=null · elapsedMs=0.
     */
    public void recordRetry(int step, String stepName, String phase, int iteration,
                            Map<String, Object> input, String reason) {
        traces.add(new StepTrace(step, stepName, phase, iteration, input, null,
            TraceStatus.RETRY, null, reason, 0));
    }

    /**
     * 사양상 미실행 step 기록 (e.g. step 14 max-wgt mode 미구현).
     */
    public void recordSkip(int step, String stepName, String phase, String reason) {
        traces.add(new StepTrace(step, stepName, phase, 1, Map.of(), null,
            TraceStatus.SKIP, null, reason, 0));
    }
}
