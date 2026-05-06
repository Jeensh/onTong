package com.ontong.slab.optimizer;

import com.ontong.slab.constraint.ConstraintViolation;
import com.ontong.slab.domain.Slab;

import java.util.List;

/**
 * 엔진이 생성한 Slab 후보. 유효성 플래그와 위반 내역을 함께 포함해
 * 호출부에서 실패 원인을 UI 에 전달할 수 있게 한다.
 */
public record DesignCandidate(Slab slab, boolean feasible, List<ConstraintViolation> violations) {

    public double weightKg() {
        return slab.weightKg();
    }
}
