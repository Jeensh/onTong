package com.ontong.slab.optimizer;

import com.ontong.slab.constraint.EquipmentConstraintChecker;
import com.ontong.slab.domain.OrderSpec;
import com.ontong.slab.domain.Slab;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Optional;

/**
 * 중량 최대화 엔진. 수주 사양 범위를 50mm 간격 그리드로 샘플링한 뒤
 * 설비 제약을 만족하는 후보 중 최대 중량을 반환한다.
 *
 * 목적식:
 *   maximize  ρ(grade) × L × W × T
 *   subject to
 *     W ≤ rollingMillMaxWidth
 *     L ≤ furnaceMaxLength
 *     minThickness ≤ T ≤ maxThickness
 *     ρ × L × W × T × 1e-9 ≤ craneMaxLoad
 *     minLength ≤ L ≤ maxLength   (수주 사양)
 *     minWidth  ≤ W ≤ maxWidth
 *     minThickness(order) ≤ T ≤ maxThickness(order)
 */
@Component
public class WeightMaximizer {

    private static final double GRID_STEP_MM = 50.0;

    /** 실측 중량 편차 보정. 압연 중 두께 변동을 흡수하는 안전계수. */
    private static final double WEIGHT_BIAS_FACTOR = 1.02;

    private final EquipmentConstraintChecker checker;

    @Autowired
    public WeightMaximizer(EquipmentConstraintChecker checker) {
        this.checker = checker;
    }

    /**
     * 수주 사양을 받아 최대 중량 후보를 반환한다. 모든 그리드 점이 제약을
     * 위반하면 Optional.empty.
     */
    public Optional<DesignCandidate> findBest(OrderSpec order) {
        List<DesignCandidate> feasible = enumerateFeasible(order);
        return feasible.stream().max(Comparator.comparingDouble(DesignCandidate::weightKg));
    }

    /**
     * 수주 사양 범위를 그리드 탐색해 제약을 만족하는 모든 후보를 수집한다.
     */
    public List<DesignCandidate> enumerateFeasible(OrderSpec order) {
        List<DesignCandidate> result = new ArrayList<>();
        for (double l = order.getMinLengthMm(); l <= order.getMaxLengthMm(); l += GRID_STEP_MM) {
            for (double w = order.getMinWidthMm(); w <= order.getMaxWidthMm(); w += GRID_STEP_MM) {
                for (double t = order.getMinThicknessMm(); t <= order.getMaxThicknessMm(); t += GRID_STEP_MM) {
                    Slab candidate = new Slab(l, w, t, order.getGrade());
                    if (checker.isValid(candidate)) {
                        result.add(new DesignCandidate(candidate, true, List.of()));
                    }
                }
            }
        }
        return result;
    }

    /**
     * 중량 편차 보정. 압연 후 실측 중량이 이론값보다 평균 2% 높게 나오는
     * 경향이 있어 목적함수 평가 전 보정한다.
     */
    public double adjustWeightBias(double rawWeightKg) {
        return rawWeightKg * WEIGHT_BIAS_FACTOR;
    }
}
