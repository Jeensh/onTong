package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.feature.sd.process.std.service.CustomerStdService;
import com.example.slabdesign.feature.sd.process.std.service.HrMaxWgtService;
import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;
import com.example.slabdesign.feature.sd.process.working.wrapper.SdErrorCode;
import com.example.slabdesign.store.sd.std.domain.entity.CustomerStdEntity;
import com.example.slabdesign.store.sd.std.domain.entity.HrMaxWgtEntity;
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
 * Unit tests for {@link SdSecondWgtHighAction} (step 6: 2차 단중상한).
 */
@ExtendWith(MockitoExtension.class)
class SdSecondWgtHighActionTest {

    @Mock HrMaxWgtService hrMaxWgtService;
    @Mock CustomerStdService customerStdService;

    @Test
    void normalCase_picksMinOfFour() {
        HrMaxWgtEntity maxWgt = new HrMaxWgtEntity();
        maxWgt.setMaxWgt(new BigDecimal("28000"));
        when(hrMaxWgtService.lookup(any(), any(), any(), any(), any())).thenReturn(maxWgt);

        CustomerStdEntity custStd = new CustomerStdEntity();
        custStd.setPkgWgtHigh(new BigDecimal("26000"));
        when(customerStdService.findFirstMatch(any(), any(), any(), any())).thenReturn(custStd);

        SdSecondWgtHighAction action = new SdSecondWgtHighAction(hrMaxWgtService, customerStdService);
        SDSlabEntity slab = sampleSlab(new BigDecimal("30000"));
        // designPendQtyHigh=50000 / productivity=0.95 ≈ 52631.58 → not the min
        action.execute(sampleOrder(new BigDecimal("50000"), new BigDecimal("0.95")), slab);

        // min(30000, 28000, 26000, 52631.xx) = 26000
        assertThat(slab.getSecondWgtHigh()).isEqualByComparingTo("26000");
    }

    @Test
    void noCustomerStd_picksMinOfThree() {
        HrMaxWgtEntity maxWgt = new HrMaxWgtEntity();
        maxWgt.setMaxWgt(new BigDecimal("28000"));
        when(hrMaxWgtService.lookup(any(), any(), any(), any(), any())).thenReturn(maxWgt);
        when(customerStdService.findFirstMatch(any(), any(), any(), any())).thenReturn(null);

        SdSecondWgtHighAction action = new SdSecondWgtHighAction(hrMaxWgtService, customerStdService);
        SDSlabEntity slab = sampleSlab(new BigDecimal("30000"));
        action.execute(sampleOrder(new BigDecimal("50000"), new BigDecimal("0.95")), slab);

        // min(30000, 28000, 52631.xx) = 28000
        assertThat(slab.getSecondWgtHigh()).isEqualByComparingTo("28000");
    }

    @Test
    void dg107_hrMaxWgtMisses_throws() {
        when(hrMaxWgtService.lookup(any(), any(), any(), any(), any())).thenReturn(null);

        SdSecondWgtHighAction action = new SdSecondWgtHighAction(hrMaxWgtService, customerStdService);
        SDSlabEntity slab = sampleSlab(new BigDecimal("30000"));

        assertThatThrownBy(() -> action.execute(sampleOrder(new BigDecimal("50000"), new BigDecimal("0.95")), slab))
            .isInstanceOf(AlgorithmException.class)
            .extracting("errorCode")
            .isEqualTo(SdErrorCode.ALG_HR_MAX_WGT_NOT_FOUND);
    }

    private SDOrderEntity sampleOrder(BigDecimal designPendQtyHigh, BigDecimal productivity) {
        SDOrderEntity o = new SDOrderEntity();
        o.setCmpCd("K");
        o.setOrgCd("K01");
        o.setOrderNo("ORD-1");
        o.setProductCd("COIL");
        o.setCustomerCd("CUST1");
        o.setConfirmedPlantCd("A1234567");
        o.setDesignPendQtyHigh(designPendQtyHigh);
        o.setProductivity(productivity);
        return o;
    }

    private SDSlabEntity sampleSlab(BigDecimal firstWgtHigh) {
        SDSlabEntity s = new SDSlabEntity();
        s.setSlabThickness(new BigDecimal("250"));
        s.setFirstWidthHigh(new BigDecimal("1250"));
        s.setFirstWgtHigh(firstWgtHigh);
        return s;
    }
}
