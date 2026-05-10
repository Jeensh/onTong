package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.feature.sd.process.std.service.CastSpecService;
import com.example.slabdesign.feature.sd.process.std.service.HrSpecService;
import com.example.slabdesign.feature.sd.process.std.service.PlantMappingService;
import com.example.slabdesign.feature.sd.process.std.service.PlantMappingService.PlantMapping;
import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;
import com.example.slabdesign.feature.sd.process.working.wrapper.SdErrorCode;
import com.example.slabdesign.store.sd.std.domain.entity.CastSpecEntity;
import com.example.slabdesign.store.sd.std.domain.entity.HrSpecEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;

/**
 * sd · working · step 3: 1차 설계가능 길이범위 산정.
 *
 *   길이하한 = max(연주설비하한길이, 열연설비하한길이)
 *   길이상한 = min(연주설비상한길이, 열연설비상한길이)
 *
 * step 2 와 달리 EDGING 미참조. 실패코드:
 *   - DG102 HR_SPEC 미존재 (재검증)
 *   - DG105 산정 길이 범위 invalid
 *
 * @author 김XX (2017-09-15 최초작성)
 * @author 박XX (2019-04-22 confirmedPlantCd 기반 재룩업으로 변경)
 *
 * 운영이슈 P-2019-0152 (2019-03-30):
 *   - confirmedPlantCd 의 SM/HR 값이 step 2 결정 결과와 달라 길이 산정 오류
 *   - 해결: step 2 와 동일한 plant 코드 재사용 + 양쪽 spec 재룩업
 *   - 2019-04 박XX 적용 후 정상화
 */
@Component
public class SdLengthRangeAction {

    private static final int STEP_NO = 3;
    private static final String STEP_NAME = "FIRST_LENGTH_RANGE";

    private final CastSpecService castSpecService;
    private final HrSpecService hrSpecService;
    private final PlantMappingService plantMapping;

    @Autowired
    public SdLengthRangeAction(CastSpecService castSpecService, HrSpecService hrSpecService,
                               PlantMappingService plantMapping) {
        this.castSpecService = castSpecService;
        this.hrSpecService = hrSpecService;
        this.plantMapping = plantMapping;
    }

    public void execute(SDOrderEntity order, SDSlabEntity slab) {
        String confirmed = order.getConfirmedPlantCd();
        char smChar = confirmed.charAt(0);
        char hrChar = confirmed.charAt(1);

        // CAST_SPEC 재룩업
        String smCd = String.valueOf(smChar);
        PlantMapping mapping = plantMapping.getMapping(smCd);
        CastSpecEntity castSpec = castSpecService.lookup(
            order.getCmpCd(), order.getOrgCd(),
            smCd, mapping.castCd(), mapping.machineCd(),
            order.getProductTypeCd());

        // HR_SPEC 재룩업 (step 2 와 동일)
        String hrCd = String.valueOf(hrChar);
        HrSpecEntity hrSpec = hrSpecService.lookup(
            order.getCmpCd(), order.getOrgCd(), hrCd, order.getProductTypeCd());
        if (hrSpec == null) {
            throw new AlgorithmException(STEP_NO, STEP_NAME, SdErrorCode.ALG_HR_SPEC_NOT_FOUND,
                "HR_SPEC 미존재 (length 산정 단계, hrPlant=" + hrCd + ")");
        }

        BigDecimal lengthLow = castSpec.getLengthLow().max(hrSpec.getLengthLow());
        BigDecimal lengthHigh = castSpec.getLengthHigh().min(hrSpec.getLengthHigh());

        // 2018-07-11 김XX: 일부 광폭재에서 castSpec.lengthHigh < hrSpec.lengthLow → 음수 범위
        // 임시 패치 (보류) — castSpec 우선시 처리
        // if (castSpec.getLengthHigh().compareTo(hrSpec.getLengthLow()) < 0) {
        //     lengthLow = castSpec.getLengthLow();
        //     lengthHigh = castSpec.getLengthHigh();
        // }

        if (lengthLow.compareTo(lengthHigh) > 0) {
            throw new AlgorithmException(STEP_NO, STEP_NAME, SdErrorCode.ALG_INVALID_LENGTH_RANGE,
                "길이 하한(" + lengthLow + ") > 상한(" + lengthHigh + ")");
        }

        slab.setFirstLengthLow(lengthLow);
        slab.setFirstLengthHigh(lengthHigh);
    }
}
