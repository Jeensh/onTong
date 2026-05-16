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
 * Unit tests for {@link SdWidthRangeAction} (step 2: 폭범위).
 */
@ExtendWith(MockitoExtension.class)
class SdWidthRangeActionTest {

    @Mock CastSpecService castSpecService;
    @Mock HrSpecService hrSpecService;
    @Mock EdgingService edgingService;
    @Mock PlantMappingService plantMapping;

    @Test
    void normalCase_setsWidthRange() {
        when(plantMapping.getMapping("A")).thenReturn(new PlantMapping("CC1", "M1"));
        when(castSpecService.lookup(any(), any(), any(), any(), any(), any())).thenReturn(castSpec("900", "1600"));
        when(hrSpecService.lookup(any(), any(), any(), any())).thenReturn(hrSpec("950", "1550"));
        EdgingGroupEntity group = new EdgingGroupEntity();
        group.setEdgingGroupCd("G1");
        when(edgingService.findGroup(any(), any(), any(), any(), any(), any())).thenReturn(group);
        EdgingSpecEntity spec = new EdgingSpecEntity();
        spec.setEdgingCapLow(new BigDecimal("-50"));
        spec.setEdgingCapHigh(new BigDecimal("50"));
        when(edgingService.findSpec(any(), any(), any())).thenReturn(spec);

        SdWidthRangeAction action = new SdWidthRangeAction(castSpecService, hrSpecService, edgingService, plantMapping);
        SDSlabEntity slab = new SDSlabEntity();
        action.execute(sampleOrder(), slab);

        // widthLow = max(900, 950, 1200-50=1150) = 1150
        // widthHigh = min(1600, 1550, 1200+50=1250) = 1250
        assertThat(slab.getFirstWidthLow()).isEqualByComparingTo("1150");
        assertThat(slab.getFirstWidthHigh()).isEqualByComparingTo("1250");
    }

    @Test
    void dg102_hrSpecMisses_throws() {
        when(plantMapping.getMapping("A")).thenReturn(new PlantMapping("CC1", "M1"));
        when(castSpecService.lookup(any(), any(), any(), any(), any(), any())).thenReturn(castSpec("900", "1600"));
        when(hrSpecService.lookup(any(), any(), any(), any())).thenReturn(null);

        SdWidthRangeAction action = new SdWidthRangeAction(castSpecService, hrSpecService, edgingService, plantMapping);
        SDSlabEntity slab = new SDSlabEntity();

        assertThatThrownBy(() -> action.execute(sampleOrder(), slab))
            .isInstanceOf(AlgorithmException.class)
            .extracting("errorCode")
            .isEqualTo(SdErrorCode.ALG_HR_SPEC_NOT_FOUND);
    }

    @Test
    void dg103_edgingGroupMisses_throws() {
        when(plantMapping.getMapping("A")).thenReturn(new PlantMapping("CC1", "M1"));
        when(castSpecService.lookup(any(), any(), any(), any(), any(), any())).thenReturn(castSpec("900", "1600"));
        when(hrSpecService.lookup(any(), any(), any(), any())).thenReturn(hrSpec("950", "1550"));
        when(edgingService.findGroup(any(), any(), any(), any(), any(), any())).thenReturn(null);

        SdWidthRangeAction action = new SdWidthRangeAction(castSpecService, hrSpecService, edgingService, plantMapping);
        SDSlabEntity slab = new SDSlabEntity();

        assertThatThrownBy(() -> action.execute(sampleOrder(), slab))
            .isInstanceOf(AlgorithmException.class)
            .extracting("errorCode")
            .isEqualTo(SdErrorCode.ALG_EDGING_GROUP_NOT_FOUND);
    }

    @Test
    void dg104_invalidWidthRange_throws() {
        when(plantMapping.getMapping("A")).thenReturn(new PlantMapping("CC1", "M1"));
        // cast widthLow=2000 > all caps → invalid
        when(castSpecService.lookup(any(), any(), any(), any(), any(), any())).thenReturn(castSpec("2000", "2100"));
        when(hrSpecService.lookup(any(), any(), any(), any())).thenReturn(hrSpec("100", "500"));
        EdgingGroupEntity group = new EdgingGroupEntity();
        group.setEdgingGroupCd("G1");
        when(edgingService.findGroup(any(), any(), any(), any(), any(), any())).thenReturn(group);
        EdgingSpecEntity spec = new EdgingSpecEntity();
        spec.setEdgingCapLow(new BigDecimal("0"));
        spec.setEdgingCapHigh(new BigDecimal("0"));
        when(edgingService.findSpec(any(), any(), any())).thenReturn(spec);

        SdWidthRangeAction action = new SdWidthRangeAction(castSpecService, hrSpecService, edgingService, plantMapping);
        SDSlabEntity slab = new SDSlabEntity();

        assertThatThrownBy(() -> action.execute(sampleOrder(), slab))
            .isInstanceOf(AlgorithmException.class)
            .extracting("errorCode")
            .isEqualTo(SdErrorCode.ALG_INVALID_WIDTH_RANGE);
    }

    private SDOrderEntity sampleOrder() {
        SDOrderEntity o = new SDOrderEntity();
        o.setCmpCd("K");
        o.setOrgCd("K01");
        o.setOrderNo("ORD-1");
        o.setProductCd("COIL");
        o.setGradeCd("SS400");
        o.setCustomerCd("CUST1");
        o.setConfirmedPlantCd("A1234567");
        o.setSelectedHrTgtWidth(new BigDecimal("1200"));
        return o;
    }

    private CastSpecEntity castSpec(String widthLow, String widthHigh) {
        CastSpecEntity c = new CastSpecEntity();
        c.setWidthLow(new BigDecimal(widthLow));
        c.setWidthHigh(new BigDecimal(widthHigh));
        return c;
    }

    private HrSpecEntity hrSpec(String widthLow, String widthHigh) {
        HrSpecEntity h = new HrSpecEntity();
        h.setWidthLow(new BigDecimal(widthLow));
        h.setWidthHigh(new BigDecimal(widthHigh));
        return h;
    }
}
