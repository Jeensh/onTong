package com.example.slabdesign.feature.sd.designer;

import com.example.slabdesign.feature.sd.process.history.action.SdHistoryAction;
import com.example.slabdesign.feature.sd.process.std.service.ProductivityService;
import com.example.slabdesign.feature.sd.process.std.service.SpecificGravityProvider;
import com.example.slabdesign.feature.sd.process.working.action.SdFinalLengthRangeAction;
import com.example.slabdesign.feature.sd.process.working.action.SdFinalWidthRangeAction;
import com.example.slabdesign.feature.sd.process.working.action.SdFirstWeightAction;
import com.example.slabdesign.feature.sd.process.working.action.SdInitialSlabWgtAction;
import com.example.slabdesign.feature.sd.process.working.action.SdLengthRangeAction;
import com.example.slabdesign.feature.sd.process.working.action.SdMaxSplitCountAction;
import com.example.slabdesign.feature.sd.process.working.action.SdOrderValidator;
import com.example.slabdesign.feature.sd.process.working.action.SdProductClassifier;
import com.example.slabdesign.feature.sd.process.working.action.SdSecondWgtHighAction;
import com.example.slabdesign.feature.sd.process.working.action.SdSecondWgtLowAction;
import com.example.slabdesign.feature.sd.process.working.action.SdSlabCountAction;
import com.example.slabdesign.feature.sd.process.working.action.SdSlabSaveAction;
import com.example.slabdesign.feature.sd.process.working.action.SdSlabWgtRecalcAction;
import com.example.slabdesign.feature.sd.process.working.action.SdSplitRangeAction;
import com.example.slabdesign.feature.sd.process.working.action.SdTargetLengthAction;
import com.example.slabdesign.feature.sd.process.working.action.SdTargetWidthAction;
import com.example.slabdesign.feature.sd.process.working.action.SdThicknessAction;
import com.example.slabdesign.feature.sd.process.working.action.SdWidthRangeAction;
import com.example.slabdesign.feature.sd.process.working.action.SelectedHrTgtWidthResolver;
import com.example.slabdesign.feature.sd.process.working.service.SlabNoSequence;
import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;
import com.example.slabdesign.feature.sd.process.working.wrapper.ProductCategory;
import com.example.slabdesign.feature.sd.process.working.wrapper.SdErrorCode;
import com.example.slabdesign.feature.sd.process.working.wrapper.ValidationResult;
import com.example.slabdesign.feature.sd.trace.TraceCollector;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * sd · designer · 단위 job 흐름 제어 (전체 알고리즘 21 step).
 *
 * Phase 1 (사전 처리):
 *   1. 정합성 점검 → fail 시 history 적재 + skip
 *   2. 제품 분류 → COIL 외 silent skip
 *   3. 작업용 필드 채움 (selectedHrTgtWidth, specificGravity, 누적 productivity)
 *
 * Phase 2 (알고리즘):
 *   - SDSlabEntity 생성 + slabNo pre-generate (12자리 sequence)
 *   - one-shot: step 1~7
 *   - A-a 루프: step 8~15 (분할수 max → 1, step 12-13 fallback)
 *   - one-shot: step 16~19 (최종 폭/길이 + 목표값)
 *   - step 20: SLAB_RESULT 매수만큼 row 저장
 *   - step 21: 각 step 별 SLAB_DESIGN_HIST 적재 (executeWithHistory wrapper)
 *
 * 실패 처리:
 *   - AlgorithmException → 해당 step history 기록 + slab.designStatus=FAIL + return null
 *   - IllegalStateException (EDGING_SPEC 미존재) propagate (사용자 사양)
 *
 * Trace (옵션):
 *   - {@code design(order)} = {@code design(order, null)} — trace 비활성 (zero overhead)
 *   - {@code design(order, trace)} — TraceCollector 가 step 별 input/output snapshot 적재
 *   - 기존 history 적재 동작은 변경 없음 — trace 는 in-memory diagnostic 채널.
 */
@Component
public class SdDesigner {

    // Phase 1
    private final SdOrderValidator validator;
    private final SdProductClassifier classifier;
    private final SelectedHrTgtWidthResolver hrResolver;
    private final SpecificGravityProvider gravityProvider;
    private final ProductivityService productivityService;

    // Phase 2 — one-shot steps 1~7
    private final SdThicknessAction thicknessAction;
    private final SdWidthRangeAction widthRangeAction;
    private final SdLengthRangeAction lengthRangeAction;
    private final SdFirstWeightAction firstWeightAction;
    private final SdSecondWgtLowAction secondWgtLowAction;
    private final SdSecondWgtHighAction secondWgtHighAction;
    private final SdMaxSplitCountAction maxSplitCountAction;

    // Phase 2 — A-a 루프 steps 8~15
    private final SdSplitRangeAction splitRangeAction;
    private final SdSlabCountAction slabCountAction;
    private final SdInitialSlabWgtAction initialSlabWgtAction;
    private final SdSlabWgtRecalcAction slabWgtRecalcAction;

    // Phase 2 — final steps 16~19 + save 20
    private final SdFinalWidthRangeAction finalWidthRangeAction;
    private final SdFinalLengthRangeAction finalLengthRangeAction;
    private final SdTargetWidthAction targetWidthAction;
    private final SdTargetLengthAction targetLengthAction;
    private final SdSlabSaveAction slabSaveAction;

    // 부속
    private final SdHistoryAction historyAction;
    private final SlabNoSequence slabNoSequence;

    @Autowired
    public SdDesigner(SdOrderValidator validator,
                      SdProductClassifier classifier,
                      SelectedHrTgtWidthResolver hrResolver,
                      SpecificGravityProvider gravityProvider,
                      ProductivityService productivityService,
                      SdThicknessAction thicknessAction,
                      SdWidthRangeAction widthRangeAction,
                      SdLengthRangeAction lengthRangeAction,
                      SdFirstWeightAction firstWeightAction,
                      SdSecondWgtLowAction secondWgtLowAction,
                      SdSecondWgtHighAction secondWgtHighAction,
                      SdMaxSplitCountAction maxSplitCountAction,
                      SdSplitRangeAction splitRangeAction,
                      SdSlabCountAction slabCountAction,
                      SdInitialSlabWgtAction initialSlabWgtAction,
                      SdSlabWgtRecalcAction slabWgtRecalcAction,
                      SdFinalWidthRangeAction finalWidthRangeAction,
                      SdFinalLengthRangeAction finalLengthRangeAction,
                      SdTargetWidthAction targetWidthAction,
                      SdTargetLengthAction targetLengthAction,
                      SdSlabSaveAction slabSaveAction,
                      SdHistoryAction historyAction,
                      SlabNoSequence slabNoSequence) {
        this.validator = validator;
        this.classifier = classifier;
        this.hrResolver = hrResolver;
        this.gravityProvider = gravityProvider;
        this.productivityService = productivityService;
        this.thicknessAction = thicknessAction;
        this.widthRangeAction = widthRangeAction;
        this.lengthRangeAction = lengthRangeAction;
        this.firstWeightAction = firstWeightAction;
        this.secondWgtLowAction = secondWgtLowAction;
        this.secondWgtHighAction = secondWgtHighAction;
        this.maxSplitCountAction = maxSplitCountAction;
        this.splitRangeAction = splitRangeAction;
        this.slabCountAction = slabCountAction;
        this.initialSlabWgtAction = initialSlabWgtAction;
        this.slabWgtRecalcAction = slabWgtRecalcAction;
        this.finalWidthRangeAction = finalWidthRangeAction;
        this.finalLengthRangeAction = finalLengthRangeAction;
        this.targetWidthAction = targetWidthAction;
        this.targetLengthAction = targetLengthAction;
        this.slabSaveAction = slabSaveAction;
        this.historyAction = historyAction;
        this.slabNoSequence = slabNoSequence;
    }

    /** Trace 미사용 default — {@code design(order, null)} 위임. */
    public SDSlabEntity design(SDOrderEntity order) {
        return design(order, null);
    }

    /**
     * 21-step 알고리즘 본체. {@code trace} 가 null 이면 trace 미적재 (zero overhead).
     */
    public SDSlabEntity design(SDOrderEntity order, TraceCollector trace) {
        // ===== Phase 1 =====
        ValidationResult result = validator.validate(order);
        if (result.isFailed()) {
            historyAction.recordValidationFailure(order, result);
            if (trace != null) {
                trace.recordSkip(0, "VALIDATION_FAILED", "PHASE_1",
                    result.getErrorCode() + " — " + result.getMessage());
            }
            return null;
        }

        ProductCategory category = classifier.classify(order);
        if (category != ProductCategory.COIL) {
            if (trace != null) {
                trace.recordSkip(0, "PRODUCT_NOT_COIL", "PHASE_1",
                    "category=" + category);
            }
            return null;
        }

        hrResolver.resolveAndSet(order);
        order.setSpecificGravity(gravityProvider.get(order.getGradeCd()));
        order.setProductivity(productivityService.cumulativeProductivity(
            order.getCmpCd(), order.getOrgCd(), order.getConfirmedPlantCd(),
            order.getGradeCd(), order.getProductCd(), order.getCustomerCd()));

        // ===== Phase 2 =====
        SDSlabEntity slab = createInitialSlab(order);

        try {
            // one-shot steps 1~7 (step별 history 적재)
            executeWithHistory(1, "SLAB_THICKNESS",          "SdThicknessAction",       order, slab, trace, thicknessAction::execute);
            executeWithHistory(2, "FIRST_WIDTH_RANGE",       "SdWidthRangeAction",      order, slab, trace, widthRangeAction::execute);
            executeWithHistory(3, "FIRST_LENGTH_RANGE",      "SdLengthRangeAction",     order, slab, trace, lengthRangeAction::execute);
            executeWithHistory(4, "FIRST_WGT_RANGE",         "SdFirstWeightAction",     order, slab, trace, firstWeightAction::execute);
            executeWithHistory(5, "SECOND_WGT_LOW",          "SdSecondWgtLowAction",    order, slab, trace, secondWgtLowAction::execute);
            executeWithHistory(6, "SECOND_WGT_HIGH",         "SdSecondWgtHighAction",   order, slab, trace, secondWgtHighAction::execute);
            executeWithHistory(7, "MAX_SPLIT_COUNT",         "SdMaxSplitCountAction",   order, slab, trace, maxSplitCountAction::execute);

            // A-a 루프 (steps 8~15, 내부 attempts silent — 수렴 시점만 history 적재)
            runAaLoop(order, slab, trace);
            historyAction.recordStep(order, slab.getSlabNo(), 15, "A_A_LOOP_CONVERGED",
                snapshotSlab(slab));

            // step 14: 제품단중 최대화 모드 — 사양상 미구현 (trace 시 SKIP 만 기록).
            if (trace != null) {
                trace.recordSkip(14, "MAX_WGT_MODE", "AA_LOOP",
                    "step 14 not implemented per spec");
            }

            // final steps 16~19 (step별 history 적재)
            executeWithHistory(16, "FINAL_WIDTH_RANGE",      "SdFinalWidthRangeAction",  order, slab, trace, finalWidthRangeAction::execute);
            executeWithHistory(17, "FINAL_LENGTH_RANGE",     "SdFinalLengthRangeAction", order, slab, trace, finalLengthRangeAction::execute);
            executeWithHistory(18, "TARGET_WIDTH",           "SdTargetWidthAction",      order, slab, trace, targetWidthAction::execute);
            executeWithHistory(19, "TARGET_LENGTH",          "SdTargetLengthAction",     order, slab, trace, targetLengthAction::execute);

            // step 20: SLAB_RESULT 매수 row 저장
            List<String> savedSlabNos = saveStep(order, slab, trace);
            historyAction.recordStep(order, slab.getSlabNo(), 20, "SLAB_RESULT_SAVED",
                "{\"savedSlabNos\":" + savedSlabNos.size() + "," + snapshotSlabBody(slab) + "}");

        } catch (AlgorithmException e) {
            historyAction.recordAlgorithmFailure(
                order, e.getStepNo(), e.getStepName(), e.getErrorCode(),
                snapshotSlab(slab));
            slab.setDesignStatus("FAIL");
            slab.setErrorCode(e.getErrorCode());
            return null;
        }

        slab.setDesignStatus("SUCCESS");
        return slab;
    }

    /**
     * A-a 루프 — 내부 iteration 은 silent (history 미적재).
     * 수렴 후 SdDesigner 가 단일 "A_A_LOOP_CONVERGED" history 1 row 적재.
     */
    private void runAaLoop(SDOrderEntity order, SDSlabEntity slab, TraceCollector trace) {
        int maxSplit = slab.getMaxSplitCountUpper();

        for (int split = maxSplit; split >= 1; split--) {
            slab.setCurrentSplitCount(split);

            if (!tryStep(8, "SdSplitRangeAction", order, slab, trace, split, splitRangeAction::execute)) continue;
            if (!tryStep(9, "SdSlabCountAction", order, slab, trace, split, slabCountAction::execute)) continue;

            if (tryStep(10, "SdInitialSlabWgtAction", order, slab, trace, split, initialSlabWgtAction::execute)) {
                return; // step 10 YES → step 11 implicit
            }
            if (tryStep(13, "SdSlabWgtRecalcAction", order, slab, trace, split, slabWgtRecalcAction::execute)) {
                return; // step 13 YES → step 15 implicit
            }
        }

        throw new AlgorithmException(8, "A_A_LOOP", SdErrorCode.ALG_NO_CONVERGENCE,
            "A-a 루프 분할수 " + maxSplit + " ~ 1 까지 모두 수렴 실패");
    }

    /** 액션 실행 + 성공 시 step별 history 적재. fail 시 outer catch 가 처리. */
    private void executeWithHistory(int stepNo, String stepName, String actionClass,
                                    SDOrderEntity order, SDSlabEntity slab,
                                    TraceCollector trace, AlgorithmStep step) {
        if (trace == null) {
            step.run(order, slab); // throws AlgorithmException on fail
        } else {
            trace.wrap(stepNo, actionClass, "ONE_SHOT", 1,
                snapshotMap(slab),
                () -> { step.run(order, slab); return snapshotMap(slab); });
        }
        historyAction.recordStep(order, slab.getSlabNo(), stepNo, stepName, snapshotSlab(slab));
    }

    /** A-a 루프 내부 silent 시도. DG108 → false (RETRY trace 적재), 다른 fail → throw. */
    private boolean tryStep(int stepNo, String actionClass,
                            SDOrderEntity order, SDSlabEntity slab,
                            TraceCollector trace, int iteration,
                            AlgorithmStep step) {
        try {
            if (trace == null) {
                step.run(order, slab);
            } else {
                trace.wrap(stepNo, actionClass, "AA_LOOP", iteration,
                    snapshotMap(slab),
                    () -> { step.run(order, slab); return snapshotMap(slab); });
            }
            return true;
        } catch (AlgorithmException e) {
            if (SdErrorCode.ALG_ITERATION_NEEDED.equals(e.getErrorCode())) {
                if (trace != null) {
                    trace.recordRetry(stepNo, actionClass, "AA_LOOP", iteration,
                        Map.of("currentSplitCount", iteration), e.getMessage());
                }
                return false;
            }
            throw e;
        }
    }

    /** step 20 SLAB_RESULT 저장 + trace. */
    private List<String> saveStep(SDOrderEntity order, SDSlabEntity slab, TraceCollector trace) {
        if (trace == null) {
            return slabSaveAction.execute(order, slab);
        }
        @SuppressWarnings("unchecked")
        List<String>[] holder = new List[1];
        trace.wrap(20, "SdSlabSaveAction", "SAVE", 1,
            snapshotMap(slab),
            () -> {
                List<String> saved = slabSaveAction.execute(order, slab);
                holder[0] = saved;
                Map<String, Object> out = new LinkedHashMap<>(snapshotMap(slab));
                out.put("savedSlabNos", saved.size());
                return out;
            });
        return holder[0];
    }

    @FunctionalInterface
    private interface AlgorithmStep {
        void run(SDOrderEntity order, SDSlabEntity slab);
    }

    /** Phase 2 진입 시 SDSlab 초기화 + slabNo pre-generate. */
    private SDSlabEntity createInitialSlab(SDOrderEntity order) {
        SDSlabEntity slab = new SDSlabEntity();
        slab.setCmpCd(order.getCmpCd());
        slab.setOrgCd(order.getOrgCd());
        slab.setSlabNo(slabNoSequence.next()); // 12자리 sequence
        slab.setOrderNo(order.getOrderNo());
        slab.setConfirmedPlantCd(order.getConfirmedPlantCd());
        slab.setPossiblePlantCd(order.getPossiblePlantCd());
        slab.setDesignStatus("IN_PROGRESS");
        return slab;
    }

    /** Slab snapshot (간단 JSON 형태) — history.SNAPSHOT 컬럼에 저장. */
    private String snapshotSlab(SDSlabEntity slab) {
        return "{" + snapshotSlabBody(slab) + "}";
    }

    private String snapshotSlabBody(SDSlabEntity slab) {
        StringBuilder sb = new StringBuilder();
        appendField(sb, "slabNo", slab.getSlabNo());
        appendField(sb, "slabThickness", slab.getSlabThickness());
        appendField(sb, "firstWidthLow", slab.getFirstWidthLow());
        appendField(sb, "firstWidthHigh", slab.getFirstWidthHigh());
        appendField(sb, "firstLengthLow", slab.getFirstLengthLow());
        appendField(sb, "firstLengthHigh", slab.getFirstLengthHigh());
        appendField(sb, "firstWgtLow", slab.getFirstWgtLow());
        appendField(sb, "firstWgtHigh", slab.getFirstWgtHigh());
        appendField(sb, "secondWgtLow", slab.getSecondWgtLow());
        appendField(sb, "secondWgtHigh", slab.getSecondWgtHigh());
        appendField(sb, "maxSplitCountUpper", slab.getMaxSplitCountUpper());
        appendField(sb, "currentSplitCount", slab.getCurrentSplitCount());
        appendField(sb, "optimalSplitCount", slab.getOptimalSplitCount());
        appendField(sb, "splitWgtLow", slab.getSplitWgtLow());
        appendField(sb, "splitWgtHigh", slab.getSplitWgtHigh());
        appendField(sb, "slabCountInProgress", slab.getSlabCountInProgress());
        appendField(sb, "slabWgtInProgress", slab.getSlabWgtInProgress());
        appendField(sb, "finalWidthLow", slab.getFinalWidthLow());
        appendField(sb, "finalWidthHigh", slab.getFinalWidthHigh());
        appendField(sb, "finalLengthLow", slab.getFinalLengthLow());
        appendField(sb, "finalLengthHigh", slab.getFinalLengthHigh());
        appendField(sb, "targetSlabWidth", slab.getTargetSlabWidth());
        appendField(sb, "targetSlabLength", slab.getTargetSlabLength());
        return sb.toString();
    }

    /** trace 용 Map snapshot (JSON 대신 in-memory Map). null safe. */
    private Map<String, Object> snapshotMap(SDSlabEntity slab) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("slabNo", slab.getSlabNo());
        m.put("slabThickness", slab.getSlabThickness());
        m.put("firstWidthLow", slab.getFirstWidthLow());
        m.put("firstWidthHigh", slab.getFirstWidthHigh());
        m.put("firstLengthLow", slab.getFirstLengthLow());
        m.put("firstLengthHigh", slab.getFirstLengthHigh());
        m.put("firstWgtLow", slab.getFirstWgtLow());
        m.put("firstWgtHigh", slab.getFirstWgtHigh());
        m.put("secondWgtLow", slab.getSecondWgtLow());
        m.put("secondWgtHigh", slab.getSecondWgtHigh());
        m.put("maxSplitCountUpper", slab.getMaxSplitCountUpper());
        m.put("currentSplitCount", slab.getCurrentSplitCount());
        m.put("optimalSplitCount", slab.getOptimalSplitCount());
        m.put("splitWgtLow", slab.getSplitWgtLow());
        m.put("splitWgtHigh", slab.getSplitWgtHigh());
        m.put("slabCountInProgress", slab.getSlabCountInProgress());
        m.put("slabWgtInProgress", slab.getSlabWgtInProgress());
        m.put("finalWidthLow", slab.getFinalWidthLow());
        m.put("finalWidthHigh", slab.getFinalWidthHigh());
        m.put("finalLengthLow", slab.getFinalLengthLow());
        m.put("finalLengthHigh", slab.getFinalLengthHigh());
        m.put("targetSlabWidth", slab.getTargetSlabWidth());
        m.put("targetSlabLength", slab.getTargetSlabLength());
        return m;
    }

    private void appendField(StringBuilder sb, String name, Object value) {
        if (sb.length() > 0) sb.append(",");
        sb.append('"').append(name).append("\":");
        if (value == null) {
            sb.append("null");
        } else {
            sb.append(value);
        }
    }
}
