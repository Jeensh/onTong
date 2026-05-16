package com.example.slabdesign.feature.sd.trace;

import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;
import com.example.slabdesign.feature.sd.process.working.wrapper.SdErrorCode;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class TraceCollectorTest {

    @Test
    void wrap_okPath_recordsOkTrace() {
        TraceCollector collector = new TraceCollector();
        Object result = collector.wrap(1, "SdThicknessAction", "ONE_SHOT", 1,
            Map.of("orderWidth", 1200.0),
            () -> Map.of("slabThickness", 230.0));
        assertThat(result).isEqualTo(Map.of("slabThickness", 230.0));
        assertThat(collector.traces()).hasSize(1);
        StepTrace t = collector.traces().get(0);
        assertThat(t.status()).isEqualTo(TraceStatus.OK);
        assertThat(t.errorCode()).isNull();
        assertThat(t.elapsedMs()).isGreaterThanOrEqualTo(0);
        assertThat(t.input()).containsEntry("orderWidth", 1200.0);
        assertThat(t.output()).containsEntry("slabThickness", 230.0);
    }

    @Test
    void wrap_algorithmException_recordsFailTraceAndRethrows() {
        TraceCollector collector = new TraceCollector();
        assertThatThrownBy(() -> collector.wrap(2, "SdWidthRangeAction", "ONE_SHOT", 1,
            Map.of(),
            () -> {
                throw new AlgorithmException(2, "SdWidthRangeAction", SdErrorCode.ALG_INVALID_WIDTH_RANGE, "invalid");
            }))
            .isInstanceOf(AlgorithmException.class);
        assertThat(collector.traces()).hasSize(1);
        StepTrace t = collector.traces().get(0);
        assertThat(t.status()).isEqualTo(TraceStatus.FAIL);
        assertThat(t.errorCode()).isEqualTo("DG104");
        assertThat(t.errorMessage()).isEqualTo("invalid");
        assertThat(t.output()).isNull();
    }

    @Test
    void recordRetry_addsRetryTrace() {
        TraceCollector collector = new TraceCollector();
        collector.recordRetry(13, "SdSlabWgtRecalcAction", "AA_LOOP", 1,
            Map.of("splitCount", 4), "weight out of range");
        assertThat(collector.traces()).hasSize(1);
        StepTrace t = collector.traces().get(0);
        assertThat(t.status()).isEqualTo(TraceStatus.RETRY);
        assertThat(t.errorMessage()).isEqualTo("weight out of range");
        assertThat(t.iteration()).isEqualTo(1);
        assertThat(t.input()).containsEntry("splitCount", 4);
    }

    @Test
    void recordSkip_addsSkipTrace() {
        TraceCollector collector = new TraceCollector();
        collector.recordSkip(14, "SdMaxWgtMode", "AA_LOOP", "step 14 not implemented per spec");
        assertThat(collector.traces()).hasSize(1);
        StepTrace t = collector.traces().get(0);
        assertThat(t.status()).isEqualTo(TraceStatus.SKIP);
        assertThat(t.errorMessage()).isEqualTo("step 14 not implemented per spec");
    }
}
