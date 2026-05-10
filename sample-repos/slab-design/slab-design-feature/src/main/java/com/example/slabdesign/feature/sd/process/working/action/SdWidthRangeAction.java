package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.feature.sd.process.std.service.CastSpecService;
import com.example.slabdesign.feature.sd.process.std.service.EdgingService;
import com.example.slabdesign.feature.sd.process.std.service.HrSpecService;
import com.example.slabdesign.feature.sd.process.std.service.PlantMappingService;
import com.example.slabdesign.feature.sd.process.std.service.PlantMappingService.PlantMapping;
import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;
import com.example.slabdesign.feature.sd.process.working.wrapper.SdErrorCode;
import com.example.slabdesign.store.sd.std.domain.entity.CastSpecEntity;
import com.example.slabdesign.store.sd.std.domain.entity.EdgingGroupEntity;
import com.example.slabdesign.store.sd.std.domain.entity.EdgingSpecEntity;
import com.example.slabdesign.store.sd.std.domain.entity.HrSpecEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;

/**
 * sd · working · step 2: 1차 설계가능 폭범위 산정.
 *
 *   폭하한 = max(연주설비하한폭, 열연설비하한폭, 열연목표폭 + EDGING_능력하한)
 *   폭상한 = min(연주설비상한폭, 열연설비상한폭, 열연목표폭 + EDGING_능력상한)
 *
 * 실패 코드:
 *   - DG102 HR_SPEC 미존재
 *   - DG103 EDGING_GROUP 미존재
 *   - DG104 산정 폭 범위 invalid
 *   - EDGING_SPEC 미존재 → IllegalStateException (사용자 사양)
 *
 * NOTE: CAST_SPEC 은 step 1 에서 이미 검증됨. 여기서는 재룩업.
 */
@Component
public class SdWidthRangeAction {

    private static final int STEP_NO = 2;
    private static final String STEP_NAME = "FIRST_WIDTH_RANGE";

    private final CastSpecService castSpecService;
    private final HrSpecService hrSpecService;
    private final EdgingService edgingService;
    private final PlantMappingService plantMapping;

    @Autowired
    public SdWidthRangeAction(CastSpecService castSpecService, HrSpecService hrSpecService,
                              EdgingService edgingService, PlantMappingService plantMapping) {
        this.castSpecService = castSpecService;
        this.hrSpecService = hrSpecService;
        this.edgingService = edgingService;
        this.plantMapping = plantMapping;
    }

    public void execute(SDOrderEntity order, SDSlabEntity slab) {
        String confirmed = order.getConfirmedPlantCd();
        char smChar = confirmed.charAt(0);
        char hrChar = confirmed.charAt(1);

        // CAST_SPEC 재룩업 (step 1 에서 검증된 케이스)
        String smCd = String.valueOf(smChar);
        PlantMapping mapping = plantMapping.getMapping(smCd);
        CastSpecEntity castSpec = castSpecService.lookup(
            order.getCmpCd(), order.getOrgCd(),
            smCd, mapping.castCd(), mapping.machineCd(),
            order.getProductTypeCd());

        // HR_SPEC
        if (hrChar == ' ') {
            throw failHr("열연 공장 비활성 (확통[1] = ' ')");
        }
        String hrCd = String.valueOf(hrChar);
        HrSpecEntity hrSpec = hrSpecService.lookup(
            order.getCmpCd(), order.getOrgCd(), hrCd, order.getProductTypeCd());
        if (hrSpec == null) {
            throw failHr("HR_SPEC 미존재 (hrPlant=" + hrCd
                + ", productType=" + order.getProductTypeCd() + ")");
        }

        // EDGING_GROUP 매칭
        BigDecimal selectedWidth = order.getSelectedHrTgtWidth();
        if (selectedWidth == null) {
            throw failEdgingGroup("selectedHrTgtWidth 미설정 — 열연 위치 매핑 실패");
        }
        EdgingGroupEntity edgingGroup = edgingService.findGroup(
            order.getCmpCd(), order.getOrgCd(),
            order.getGradeCd(), order.getProductTypeCd(), order.getCustomerCd(),
            selectedWidth);
        if (edgingGroup == null) {
            throw failEdgingGroup("EDGING_GROUP 매칭 실패 (grade=" + order.getGradeCd()
                + ", product=" + order.getProductTypeCd() + ", customer=" + order.getCustomerCd()
                + ", width=" + selectedWidth + ")");
        }

        // EDGING_SPEC ('*' fallback, 미존재 시 IllegalStateException — 사용자 사양)
        EdgingSpecEntity edgingSpec = edgingService.findSpec(
            order.getCmpCd(), order.getOrgCd(), edgingGroup.getEdgingGroupCd());

        // 폭하한 = max(연주하한, 열연하한, 열연목표폭+EDGING하한)
        BigDecimal widthLow = max3(
            castSpec.getWidthLow(),
            hrSpec.getWidthLow(),
            selectedWidth.add(edgingSpec.getEdgingCapLow()));
        BigDecimal widthHigh = min3(
            castSpec.getWidthHigh(),
            hrSpec.getWidthHigh(),
            selectedWidth.add(edgingSpec.getEdgingCapHigh()));

        if (widthLow.compareTo(widthHigh) > 0) {
            throw new AlgorithmException(STEP_NO, STEP_NAME, SdErrorCode.ALG_INVALID_WIDTH_RANGE,
                "폭 하한(" + widthLow + ") > 상한(" + widthHigh + ")");
        }

        slab.setFirstWidthLow(widthLow);
        slab.setFirstWidthHigh(widthHigh);
    }

    private AlgorithmException failHr(String msg) {
        return new AlgorithmException(STEP_NO, STEP_NAME, SdErrorCode.ALG_HR_SPEC_NOT_FOUND, msg);
    }

    private AlgorithmException failEdgingGroup(String msg) {
        return new AlgorithmException(STEP_NO, STEP_NAME, SdErrorCode.ALG_EDGING_GROUP_NOT_FOUND, msg);
    }

    private static BigDecimal max3(BigDecimal a, BigDecimal b, BigDecimal c) {
        return a.max(b).max(c);
    }

    private static BigDecimal min3(BigDecimal a, BigDecimal b, BigDecimal c) {
        return a.min(b).min(c);
    }
}
