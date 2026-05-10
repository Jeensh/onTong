package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.feature.sd.process.std.service.CastSpecService;
import com.example.slabdesign.feature.sd.process.std.service.PlantMappingService;
import com.example.slabdesign.feature.sd.process.std.service.PlantMappingService.PlantMapping;
import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;
import com.example.slabdesign.feature.sd.process.working.wrapper.SdErrorCode;
import com.example.slabdesign.store.sd.std.domain.entity.CastSpecEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/**
 * sd · working · step 1: slab 두께 결정.
 *
 * 룩업 흐름:
 *   1. SDOrder.confirmedPlantCd[0] (제강 위치) → smCd
 *   2. PlantMappingService.getMapping(smCd) → (castCd, machineCd)
 *   3. CastSpecService.lookup(회사/소/제강/연주/머신/품종) → CastSpecEntity
 *   4. CastSpecEntity.slabThickness → SDSlabEntity.slabThickness
 *
 * 실패 시 AlgorithmException (DG101) — SdDesigner 가 catch + history 적재.
 */
@Component
public class SdThicknessAction {

    private static final int STEP_NO = 1;
    private static final String STEP_NAME = "SLAB_THICKNESS";

    private final CastSpecService castSpecService;
    private final PlantMappingService plantMapping;

    @Autowired
    public SdThicknessAction(CastSpecService castSpecService, PlantMappingService plantMapping) {
        this.castSpecService = castSpecService;
        this.plantMapping = plantMapping;
    }

    public void execute(SDOrderEntity order, SDSlabEntity slab) {
        String confirmed = order.getConfirmedPlantCd();
        if (confirmed == null || confirmed.isEmpty()) {
            throw fail("확정통과공장코드 미설정");
        }
        char smChar = confirmed.charAt(0);
        if (smChar == ' ') {
            throw fail("제강 공장 비활성 (확통[0] = ' ')");
        }
        String smCd = String.valueOf(smChar);

        PlantMapping mapping = plantMapping.getMapping(smCd);
        if (mapping == null) {
            throw fail("PlantMapping 미정의 for smCd=" + smCd);
        }

        CastSpecEntity spec = castSpecService.lookup(
            order.getCmpCd(), order.getOrgCd(),
            smCd, mapping.castCd(), mapping.machineCd(),
            order.getProductTypeCd());
        if (spec == null) {
            throw fail("CAST_SPEC 미존재 (sm=" + smCd
                + ", cast=" + mapping.castCd() + ", machine=" + mapping.machineCd()
                + ", productType=" + order.getProductTypeCd() + ")");
        }
        if (spec.getSlabThickness() == null) {
            throw fail("CAST_SPEC.SLAB_THICKNESS NULL");
        }

        slab.setSlabThickness(spec.getSlabThickness());
    }

    private AlgorithmException fail(String message) {
        return new AlgorithmException(STEP_NO, STEP_NAME, SdErrorCode.ALG_CAST_SPEC_NOT_FOUND, message);
    }
}
