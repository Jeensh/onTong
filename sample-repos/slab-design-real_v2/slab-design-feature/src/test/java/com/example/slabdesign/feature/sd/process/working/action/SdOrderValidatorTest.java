package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.feature.sd.process.working.wrapper.SdErrorCode;
import com.example.slabdesign.feature.sd.process.working.wrapper.ValidationResult;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Unit tests for {@link SdOrderValidator}.
 *
 * Covers DG001 (재고주문) ~ DG005 (작업기한일) per Phase 1 점검 spec.
 * v2 의 SdOrderValidator 는 dependency-free POJO 이므로 Mockito 불필요.
 * validate() 는 throw 대신 ValidationResult 반환 — pass/fail + errorCode 검증.
 */
class SdOrderValidatorTest {

    private final SdOrderValidator validator = new SdOrderValidator();

    // ============================================================
    // DG001 — 재고주문
    // ============================================================

    @Test
    void dg001_stockOrder_returnsFail() {
        SDOrderEntity order = newValidOrder();
        order.setStockCode(1); // 재고주문 마커

        ValidationResult result = validator.validate(order);

        assertThat(result.isFailed()).isTrue();
        assertThat(result.getErrorCode()).isEqualTo(SdErrorCode.VAL_STOCK_ORDER);
    }

    // ============================================================
    // DG002 — 주문 폭/길이
    // ============================================================

    @Test
    void dg002_zeroOrderWidth_returnsFail() {
        SDOrderEntity order = newValidOrder();
        order.setOrderWidth(BigDecimal.ZERO);

        ValidationResult result = validator.validate(order);

        assertThat(result.isFailed()).isTrue();
        assertThat(result.getErrorCode()).isEqualTo(SdErrorCode.VAL_ORDER_SIZE);
    }

    @Test
    void dg002_nullOrderLength_returnsFail() {
        SDOrderEntity order = newValidOrder();
        order.setOrderLength(null);

        ValidationResult result = validator.validate(order);

        assertThat(result.isFailed()).isTrue();
        assertThat(result.getErrorCode()).isEqualTo(SdErrorCode.VAL_ORDER_SIZE);
    }

    // ============================================================
    // DG003 — 포장단중 range integrity
    // ============================================================

    @Test
    void dg003_pkgWgtLowGreaterThanHigh_returnsFail() {
        SDOrderEntity order = newValidOrder();
        order.setPkgWgtLow(new BigDecimal("5000"));
        order.setPkgWgtHigh(new BigDecimal("3000"));

        ValidationResult result = validator.validate(order);

        assertThat(result.isFailed()).isTrue();
        assertThat(result.getErrorCode()).isEqualTo(SdErrorCode.VAL_PKG_WGT_RANGE);
    }

    @Test
    void dg003_negativePkgWgtLow_returnsFail() {
        SDOrderEntity order = newValidOrder();
        order.setPkgWgtLow(new BigDecimal("-1"));

        ValidationResult result = validator.validate(order);

        assertThat(result.isFailed()).isTrue();
        assertThat(result.getErrorCode()).isEqualTo(SdErrorCode.VAL_PKG_WGT_RANGE);
    }

    // ============================================================
    // DG004 — 설계대기량 + cross-table
    // ============================================================

    @Test
    void dg004_designPendQtyHighBelowPkgWgtLow_returnsFail() {
        SDOrderEntity order = newValidOrder();
        // pkgWgtLow=1000 ; designPendQtyHigh=500 → cross-check fail
        order.setDesignPendQtyHigh(new BigDecimal("500"));

        ValidationResult result = validator.validate(order);

        assertThat(result.isFailed()).isTrue();
        assertThat(result.getErrorCode()).isEqualTo(SdErrorCode.VAL_DESIGN_PEND_QTY);
    }

    // ============================================================
    // DG005 — 작업기한일
    // ============================================================

    @Test
    void dg005_pastDueDate_returnsFail() {
        SDOrderEntity order = newValidOrder();
        order.setSmDue(LocalDate.now().minusDays(1)); // 활성 공정 (확통[0]='1') 의 due 가 과거

        ValidationResult result = validator.validate(order);

        assertThat(result.isFailed()).isTrue();
        assertThat(result.getErrorCode()).isEqualTo(SdErrorCode.VAL_WORK_DUE);
    }

    @Test
    void dg005_inactiveProcessDueIgnored_returnsPass() {
        SDOrderEntity order = newValidOrder();
        // 확통[2]='HRF' 공정 비활성 ' ' — hrfDue 가 과거여도 skip 되어야 함
        order.setConfirmedPlantCd("12 45678"); // 8자리, hrf 자리 비활성
        order.setHrfDue(LocalDate.now().minusDays(10));

        ValidationResult result = validator.validate(order);

        assertThat(result.isPassed()).isTrue();
    }

    // ============================================================
    // Happy path
    // ============================================================

    @Test
    void allValidationsPass_returnsPass() {
        SDOrderEntity order = newValidOrder();

        ValidationResult result = validator.validate(order);

        assertThat(result.isPassed()).isTrue();
        assertThat(result.getErrorCode()).isNull();
    }

    // ============================================================
    // Fixture builder — 모든 5종 점검을 통과하는 valid order.
    // ============================================================

    private SDOrderEntity newValidOrder() {
        SDOrderEntity o = new SDOrderEntity();
        o.setCmpCd("K");
        o.setOrgCd("K01");
        o.setOrderNo("ORD20260510001");
        o.setStockCode(0); // 일반 주문
        o.setOrderWidth(new BigDecimal("1200"));
        o.setOrderLength(new BigDecimal("8500"));
        // DG003 포장단중 정합성
        o.setPkgWgtLow(new BigDecimal("1000"));
        o.setPkgWgtHigh(new BigDecimal("5000"));
        // DG004 설계대기량
        o.setDesignPendQty(new BigDecimal("3000"));
        o.setDesignPendQtyHigh(new BigDecimal("4000"));
        o.setDesignPendQtyLow(new BigDecimal("1500"));
        // DG005 confirmedPlantCd 8자리 + 모든 활성공정 due 미래
        o.setConfirmedPlantCd("12345678"); // 8자리 모두 활성
        LocalDate future = LocalDate.now().plusDays(30);
        o.setSmDue(future);
        o.setHrDue(future);
        o.setHrfDue(future);
        o.setCrDue(future);
        o.setAnl1Due(future);
        o.setAnl2Due(future);
        o.setGalDue(future);
        o.setCrfDue(future);
        o.setWorkDue(future);
        return o;
    }
}
