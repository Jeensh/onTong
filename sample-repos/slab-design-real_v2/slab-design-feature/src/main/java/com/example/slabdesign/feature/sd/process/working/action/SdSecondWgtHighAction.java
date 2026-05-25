package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.feature.sd.common.SdConstants;
import com.example.slabdesign.feature.sd.process.std.service.CustomerStdService;
import com.example.slabdesign.feature.sd.process.std.service.HrMaxWgtService;
import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;
import com.example.slabdesign.feature.sd.process.working.wrapper.SdErrorCode;
import com.example.slabdesign.store.sd.std.domain.entity.CustomerStdEntity;
import com.example.slabdesign.store.sd.std.domain.entity.HrMaxWgtEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.MathContext;

/**
 * sd · working · step 6: 2차 설계가능 단중상한 산정.
 *
 *   단중상한 = min(1차단중상한, 압연max단중상한, 특정고객사단중상한, 실수율고려설계대기량상한)
 *
 * 룩업 폭 기준은 firstWidthHigh (주문 폭 ≠ Slab 폭일 수 있음).
 * CUSTOMER_STD 매칭은 우선순위 검색 (firstMatch) 으로 다중 행 fallback 지원.
 */
@Component
public class SdSecondWgtHighAction {

    private static final int STEP_NO = 6;
    private static final String STEP_NAME = "SECOND_WGT_HIGH";

    /** 절대 limit — 어느 Slab도 이 단중을 넘을 수 없음 (운영 안전 sentinel). */
    private static final BigDecimal ABSOLUTE_MAX_KG = BigDecimal.valueOf(SdConstants.NO_UPPER_BOUND);

    private final HrMaxWgtService hrMaxWgtService;
    private final CustomerStdService customerStdService;

    @Autowired
    public SdSecondWgtHighAction(HrMaxWgtService hrMaxWgtService,
                                 CustomerStdService customerStdService) {
        this.hrMaxWgtService = hrMaxWgtService;
        this.customerStdService = customerStdService;
    }

    public void execute(SDOrderEntity order, SDSlabEntity slab) {
        // 확통[1] = 열연 위치
        String hrCd = String.valueOf(order.getConfirmedPlantCd().charAt(1));

        // ---------- 압연 MAX 단중 (필수, miss → DG107) ----------
        HrMaxWgtEntity maxWgt = hrMaxWgtService.lookup(
            order.getCmpCd(), order.getOrgCd(), hrCd,
            slab.getSlabThickness(), slab.getFirstWidthHigh());
        if (maxWgt == null) {
            throw new AlgorithmException(STEP_NO, STEP_NAME, SdErrorCode.ALG_HR_MAX_WGT_NOT_FOUND,
                "HR_MAX_WGT 미존재 (hr=" + hrCd
                    + ", thickness=" + slab.getSlabThickness()
                    + ", width=" + slab.getFirstWidthHigh() + ")");
        }

        // ---------- 고객사 단중 상한 (옵션, miss → 제한 없음) ----------
        // 특정고객사 제한이 적용 가능한 경우만 매칭됨
        CustomerStdEntity custStd = customerStdService.findFirstMatch(
            order.getCmpCd(), order.getOrgCd(),
            order.getProductCd(),
            order.getCustomerCd());

        // ---------- 실수율고려 설계대기량 상한 ----------
        // 실수율(yield rate) 이 작을수록 더 많은 raw material 필요 → Slab 단중 상한 증가
        // 공식: designPendQtyHigh / productivity (kg)
        BigDecimal yieldAdjustedDesignPendHigh = order.getDesignPendQtyHigh()
            .divide(order.getProductivity(), MathContext.DECIMAL64);

        // ---------- min 계산 ----------
        // 4개 한도 중 가장 작은 것 (CUSTOMER_STD 는 옵션이라 별도 분기)
        BigDecimal min = slab.getFirstWgtHigh()
            .min(maxWgt.getMaxWgt())
            .min(yieldAdjustedDesignPendHigh);
        // 고객사 제한이 있을 때만 추가로 min 적용
        if (custStd != null) {
            // 고객사 row 가 있어도 PKG_WGT_HIGH 가 NULL 일 수 있음 (특정 케이스: 하한만 있는 경우)
            if (custStd.getPkgWgtHigh() != null) {
                if (custStd.getPkgWgtHigh().compareTo(BigDecimal.ZERO) > 0) {
                    min = min.min(custStd.getPkgWgtHigh());
                }
                // else: 비양수 — 데이터 오류, 무시
            }
        }

        // 최후 안전장치 — ABSOLUTE_MAX_KG 절대 초과 금지
        if (min.compareTo(ABSOLUTE_MAX_KG) > 0) {
            min = ABSOLUTE_MAX_KG;
        }

        slab.setSecondWgtHigh(min);
    }
}
