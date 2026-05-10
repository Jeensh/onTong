package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.feature.sd.process.std.service.CustomerStdService;
import com.example.slabdesign.feature.sd.process.std.service.HrMinWgtService;
import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;
import com.example.slabdesign.feature.sd.process.working.wrapper.SdErrorCode;
import com.example.slabdesign.store.sd.std.domain.entity.CustomerStdEntity;
import com.example.slabdesign.store.sd.std.domain.entity.HrMinWgtEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;

/**
 * sd · working · step 5: 2차 설계가능 단중하한 산정.
 *
 *   단중하한 = max(1차단중하한, 특정고객사단중하한, 압연Min단중)
 *
 *   - HR_MIN_WGT 룩업 (필수, miss → DG106)
 *   - CUSTOMER_STD 룩업 (옵션, miss → 제한 없음 = max 계산에서 제외)
 *
 * HR_MIN_WGT 룩업 입력: (slab.thickness, slab.firstWidthLow) — 작은 폭에서의 MIN 제약 적용.
 */
@Component
public class SdSecondWgtLowAction {

    private static final int STEP_NO = 5;
    private static final String STEP_NAME = "SECOND_WGT_LOW";

    private final HrMinWgtService hrMinWgtService;
    private final CustomerStdService customerStdService;

    @Autowired
    public SdSecondWgtLowAction(HrMinWgtService hrMinWgtService,
                                CustomerStdService customerStdService) {
        this.hrMinWgtService = hrMinWgtService;
        this.customerStdService = customerStdService;
    }

    public void execute(SDOrderEntity order, SDSlabEntity slab) {
        String hrCd = String.valueOf(order.getConfirmedPlantCd().charAt(1));

        // 압연 MIN 단중 (필수)
        HrMinWgtEntity minWgt = hrMinWgtService.lookup(
            order.getCmpCd(), order.getOrgCd(), hrCd,
            slab.getSlabThickness(), slab.getFirstWidthLow());
        if (minWgt == null) {
            throw new AlgorithmException(STEP_NO, STEP_NAME, SdErrorCode.ALG_HR_MIN_WGT_NOT_FOUND,
                "HR_MIN_WGT 미존재 (hr=" + hrCd
                    + ", thickness=" + slab.getSlabThickness()
                    + ", width=" + slab.getFirstWidthLow() + ")");
        }

        // 고객사 단중 하한 (옵션)
        CustomerStdEntity custStd = customerStdService.findFirstMatch(
            order.getCmpCd(), order.getOrgCd(),
            order.getProductTypeCd(),    // legacy mess: PRODUCT_NAME_CD 컬럼이지만 동일 값
            order.getCustomerCd());

        BigDecimal max = slab.getFirstWgtLow().max(minWgt.getMinWgt());
        if (custStd != null && custStd.getPkgWgtLow() != null) {
            max = max.max(custStd.getPkgWgtLow());
        }
        slab.setSecondWgtLow(max);
    }
}
