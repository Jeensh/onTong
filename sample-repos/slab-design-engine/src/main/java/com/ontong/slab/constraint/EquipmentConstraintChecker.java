package com.ontong.slab.constraint;

import com.ontong.slab.config.EquipmentProperties;
import com.ontong.slab.domain.Slab;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

/**
 * 설비 제약 검증기. 개별 제약별 메서드로 분리해 어떤 규칙이 깨졌는지
 * 역추적 가능하도록 한다.
 *
 * 검증 대상 규칙:
 *  - slab 폭은 압연기 최대 폭 이하여야 한다.
 *  - slab 길이는 가열로 최대 길이 이하여야 한다.
 *  - slab 두께는 최소 두께 이상, 최대 두께 이하여야 한다.
 *  - slab 중량은 크레인 최대 하중을 초과할 수 없다.
 */
@Component
public class EquipmentConstraintChecker {

    private final EquipmentProperties equipment;

    public EquipmentConstraintChecker(EquipmentProperties equipment) {
        this.equipment = equipment;
    }

    /**
     * 모든 설비 제약을 검증한다. 위반이 없으면 빈 리스트.
     */
    public List<ConstraintViolation> validate(Slab slab) {
        List<ConstraintViolation> violations = new ArrayList<>();
        checkRollingMillWidth(slab, violations);
        checkFurnaceLength(slab, violations);
        checkThicknessRange(slab, violations);
        checkCraneLoad(slab, violations);
        return violations;
    }

    /**
     * 압연기 최대 폭 제약. Slab 폭이 설비 한계를 초과하면 압연 불가.
     */
    private void checkRollingMillWidth(Slab slab, List<ConstraintViolation> out) {
        if (slab.getWidthMm() > equipment.getRollingMillMaxWidthMm()) {
            out.add(new ConstraintViolation(
                    "ROLLING_MILL_WIDTH",
                    "slab width " + slab.getWidthMm() + "mm exceeds rolling mill max " + equipment.getRollingMillMaxWidthMm() + "mm"));
        }
    }

    /**
     * 가열로 최대 길이 제약.
     */
    private void checkFurnaceLength(Slab slab, List<ConstraintViolation> out) {
        if (slab.getLengthMm() > equipment.getFurnaceMaxLengthMm()) {
            out.add(new ConstraintViolation(
                    "FURNACE_LENGTH",
                    "slab length " + slab.getLengthMm() + "mm exceeds furnace max " + equipment.getFurnaceMaxLengthMm() + "mm"));
        }
    }

    /**
     * 두께 범위 제약. 최소 두께 이상, 최대 두께 이하.
     * 최대 두께 상한은 현재 240mm 로 하드 체크한다.
     */
    private void checkThicknessRange(Slab slab, List<ConstraintViolation> out) {
        if (slab.getThicknessMm() < equipment.getMinThicknessMm()) {
            out.add(new ConstraintViolation(
                    "MIN_THICKNESS",
                    "slab thickness " + slab.getThicknessMm() + "mm is below min " + equipment.getMinThicknessMm() + "mm"));
        }
        if (slab.getThicknessMm() > equipment.getMaxThicknessMm()) {
            out.add(new ConstraintViolation(
                    "MAX_THICKNESS",
                    "slab thickness " + slab.getThicknessMm() + "mm exceeds max " + equipment.getMaxThicknessMm() + "mm"));
        }
    }

    /**
     * 크레인 최대 하중 제약. Slab 중량이 한계를 넘으면 이동 불가.
     */
    private void checkCraneLoad(Slab slab, List<ConstraintViolation> out) {
        if (slab.weightKg() > equipment.getCraneMaxLoadKg()) {
            out.add(new ConstraintViolation(
                    "CRANE_LOAD",
                    "slab weight " + slab.weightKg() + "kg exceeds crane max " + equipment.getCraneMaxLoadKg() + "kg"));
        }
    }

    public boolean isValid(Slab slab) {
        return validate(slab).isEmpty();
    }
}
