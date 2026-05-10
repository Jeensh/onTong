package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.feature.sd.common.SdConstants;
import com.example.slabdesign.feature.sd.process.working.wrapper.SdErrorCode;
import com.example.slabdesign.feature.sd.process.working.wrapper.ValidationResult;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * sd · working · 주문 정합성 점검 통합 Validator.
 *
 * Phase 1 의 5종 점검을 한 클래스로 통합 (사용자 지정).
 * 첫 실패 시 즉시 fail 반환 — 나머지 점검 skip (short-circuit).
 *
 * 에러코드 매핑:
 *   DG001 — 재고주문 (STOCK_CODE=1 → FAIL)
 *   DG002 — 주문 폭/길이 (둘 다 양수 아니면 FAIL)
 *   DG003 — 포장단중 range integrity (하/상한 양수 + 하한 ≤ 상한)
 *   DG004 — 설계대기량 양수 + 상한 ≥ 포장단중하한 (cross-table check)
 *   DG005 — 작업기한일 (활성공정 8 due + ORDER_OM.WORK_DUE 모두 미래 날짜)
 */
@Component
public class SdOrderValidator {

    /** 8 공정 한국명 (에러 메시지용). */
    private static final String[] PROCESS_NAMES = {
        "제강", "열연", "열연정정", "냉연", "1차소둔", "2차소둔", "도금", "냉연정정"
    };

    public ValidationResult validate(SDOrderEntity order) {
        ValidationResult r;

        if ((r = checkStockOrder(order)) != null) return r;
        if ((r = checkOrderSize(order)) != null) return r;
        if ((r = checkPkgWgtRange(order)) != null) return r;
        if ((r = checkDesignPendQty(order)) != null) return r;
        if ((r = checkWorkDue(order)) != null) return r;

        return ValidationResult.pass();
    }

    /** DG001: 재고주문 (STOCK_CODE=1 → FAIL). */
    private ValidationResult checkStockOrder(SDOrderEntity o) {
        if (Integer.valueOf(1).equals(o.getStockCode())) {
            return ValidationResult.fail(SdErrorCode.VAL_STOCK_ORDER,
                "재고주문 — 새 슬랩 설계 대상 아님");
        }
        return null;
    }

    /** DG002: 주문 폭·길이 양수. */
    private ValidationResult checkOrderSize(SDOrderEntity o) {
        if (!isPositive(o.getOrderWidth())) {
            return ValidationResult.fail(SdErrorCode.VAL_ORDER_SIZE,
                "주문 폭이 양수 아님 (NULL/0/음수)");
        }
        if (!isPositive(o.getOrderLength())) {
            return ValidationResult.fail(SdErrorCode.VAL_ORDER_SIZE,
                "주문 길이가 양수 아님 (NULL/0/음수)");
        }
        return null;
    }

    /** DG003: 포장단중 range integrity. */
    private ValidationResult checkPkgWgtRange(SDOrderEntity o) {
        if (!isPositive(o.getPkgWgtLow()) || !isPositive(o.getPkgWgtHigh())) {
            return ValidationResult.fail(SdErrorCode.VAL_PKG_WGT_RANGE,
                "포장 단중 하/상한이 양수 아님");
        }
        if (o.getPkgWgtLow().compareTo(o.getPkgWgtHigh()) > 0) {
            return ValidationResult.fail(SdErrorCode.VAL_PKG_WGT_RANGE,
                "포장 단중 하한 > 상한 (range integrity violation)");
        }
        return null;
    }

    /** DG004: 설계대기량 양수 + 상한 ≥ 포장단중 하한. */
    private ValidationResult checkDesignPendQty(SDOrderEntity o) {
        if (!isPositive(o.getDesignPendQty())) {
            return ValidationResult.fail(SdErrorCode.VAL_DESIGN_PEND_QTY,
                "설계대기량이 양수 아님");
        }
        if (!isPositive(o.getDesignPendQtyHigh())) {
            return ValidationResult.fail(SdErrorCode.VAL_DESIGN_PEND_QTY,
                "설계대기량 상한이 양수 아님");
        }
        if (!isPositive(o.getDesignPendQtyLow())) {
            return ValidationResult.fail(SdErrorCode.VAL_DESIGN_PEND_QTY,
                "설계대기량 하한이 양수 아님");
        }
        // Cross-table: 설계대기량 상한 ≥ 포장단중 하한
        if (o.getPkgWgtLow() != null
            && o.getDesignPendQtyHigh().compareTo(o.getPkgWgtLow()) < 0) {
            return ValidationResult.fail(SdErrorCode.VAL_DESIGN_PEND_QTY,
                "설계대기량 상한 < 포장단중 하한 — 설계 가능한 양이 최소 포장 단위 미만");
        }
        return null;
    }

    /**
     * DG005: 작업기한일. 활성 공정의 due + ORDER_OM.WORK_DUE 모두 NULL 아니고 오늘 이후.
     */
    private ValidationResult checkWorkDue(SDOrderEntity o) {
        LocalDate today = LocalDate.now();

        // ORDER_OS 의 8 공정 due 점검 (활성 공정만)
        String confirmed = o.getConfirmedPlantCd();
        if (confirmed == null || confirmed.length() < SdConstants.CONFIRMED_PLANT_CD_LENGTH) {
            return ValidationResult.fail(SdErrorCode.VAL_WORK_DUE,
                "확정통과공장코드 형식 오류 (" + SdConstants.CONFIRMED_PLANT_CD_LENGTH + "자리 필요)");
        }
        LocalDate[] dues = {
            o.getSmDue(), o.getHrDue(), o.getHrfDue(), o.getCrDue(),
            o.getAnl1Due(), o.getAnl2Due(), o.getGalDue(), o.getCrfDue()
        };
        for (int i = 0; i < SdConstants.CONFIRMED_PLANT_CD_LENGTH; i++) {
            char plantChar = confirmed.charAt(i);
            if (plantChar == SdConstants.INACTIVE_PROCESS) continue; // 비활성 공정은 점검 skip
            LocalDate due = dues[i];
            if (due == null || !due.isAfter(today)) {
                return ValidationResult.fail(SdErrorCode.VAL_WORK_DUE,
                    PROCESS_NAMES[i] + " 작업기한일 미설정 또는 과거 날짜");
            }
        }

        // ORDER_OM.WORK_DUE 점검
        if (o.getWorkDue() == null || !o.getWorkDue().isAfter(today)) {
            return ValidationResult.fail(SdErrorCode.VAL_WORK_DUE,
                "ORDER_OM 작업기한일 미설정 또는 과거 날짜");
        }

        return null;
    }

    private boolean isPositive(BigDecimal v) {
        return v != null && v.compareTo(BigDecimal.ZERO) > 0;
    }
}
