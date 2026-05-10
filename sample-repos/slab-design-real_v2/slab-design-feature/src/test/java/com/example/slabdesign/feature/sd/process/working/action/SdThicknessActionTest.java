package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.feature.sd.process.std.service.CastSpecService;
import com.example.slabdesign.feature.sd.process.std.service.PlantMappingService;
import com.example.slabdesign.feature.sd.process.std.service.PlantMappingService.PlantMapping;
import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;
import com.example.slabdesign.feature.sd.process.working.wrapper.SdErrorCode;
import com.example.slabdesign.store.sd.std.domain.entity.CastSpecEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link SdThicknessAction} (step 1: 두께 결정).
 *
 * Covers normal lookup and DG101 fail paths.
 */
@ExtendWith(MockitoExtension.class)
class SdThicknessActionTest {

    @Mock CastSpecService castSpecService;
    @Mock PlantMappingService plantMapping;

    @Test
    void normalCase_setsSlabThickness() {
        when(plantMapping.getMapping("A")).thenReturn(new PlantMapping("CC1", "M1"));
        CastSpecEntity spec = new CastSpecEntity();
        spec.setSlabThickness(new BigDecimal("250.0"));
        when(castSpecService.lookup(any(), any(), any(), any(), any(), any())).thenReturn(spec);

        SdThicknessAction action = new SdThicknessAction(castSpecService, plantMapping);
        SDSlabEntity slab = new SDSlabEntity();
        action.execute(sampleOrder(), slab);

        assertThat(slab.getSlabThickness()).isEqualByComparingTo("250.0");
    }

    @Test
    void dg101_castSpecMisses_throws() {
        when(plantMapping.getMapping("A")).thenReturn(new PlantMapping("CC1", "M1"));
        when(castSpecService.lookup(any(), any(), any(), any(), any(), any())).thenReturn(null);

        SdThicknessAction action = new SdThicknessAction(castSpecService, plantMapping);
        SDSlabEntity slab = new SDSlabEntity();

        assertThatThrownBy(() -> action.execute(sampleOrder(), slab))
            .isInstanceOf(AlgorithmException.class)
            .extracting("errorCode")
            .isEqualTo(SdErrorCode.ALG_CAST_SPEC_NOT_FOUND);
    }

    @Test
    void dg101_plantMappingMisses_throws() {
        when(plantMapping.getMapping("A")).thenReturn(null);

        SdThicknessAction action = new SdThicknessAction(castSpecService, plantMapping);
        SDSlabEntity slab = new SDSlabEntity();

        assertThatThrownBy(() -> action.execute(sampleOrder(), slab))
            .isInstanceOf(AlgorithmException.class)
            .extracting("errorCode")
            .isEqualTo(SdErrorCode.ALG_CAST_SPEC_NOT_FOUND);
    }

    @Test
    void dg101_inactiveSmProcess_throws() {
        SDOrderEntity order = sampleOrder();
        order.setConfirmedPlantCd(" 2345678"); // sm position blank

        SdThicknessAction action = new SdThicknessAction(castSpecService, plantMapping);
        SDSlabEntity slab = new SDSlabEntity();

        assertThatThrownBy(() -> action.execute(order, slab))
            .isInstanceOf(AlgorithmException.class)
            .extracting("errorCode")
            .isEqualTo(SdErrorCode.ALG_CAST_SPEC_NOT_FOUND);
    }

    private SDOrderEntity sampleOrder() {
        SDOrderEntity o = new SDOrderEntity();
        o.setCmpCd("K");
        o.setOrgCd("K01");
        o.setOrderNo("ORD-1");
        o.setProductCd("COIL");
        o.setConfirmedPlantCd("A1234567");
        return o;
    }
}
