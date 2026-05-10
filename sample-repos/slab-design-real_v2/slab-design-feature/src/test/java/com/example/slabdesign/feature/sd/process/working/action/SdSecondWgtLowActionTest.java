package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.feature.sd.process.std.service.CustomerStdService;
import com.example.slabdesign.feature.sd.process.std.service.HrMinWgtService;
import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;
import com.example.slabdesign.feature.sd.process.working.wrapper.SdErrorCode;
import com.example.slabdesign.store.sd.std.domain.entity.CustomerStdEntity;
import com.example.slabdesign.store.sd.std.domain.entity.HrMinWgtEntity;
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
 * Unit tests for {@link SdSecondWgtLowAction} (step 5: 2차 단중하한).
 */
@ExtendWith(MockitoExtension.class)
class SdSecondWgtLowActionTest {

    @Mock HrMinWgtService hrMinWgtService;
    @Mock CustomerStdService customerStdService;

    @Test
    void normalCase_picksMaxOfThree() {
        HrMinWgtEntity minWgt = new HrMinWgtEntity();
        minWgt.setMinWgt(new BigDecimal("12000"));
        when(hrMinWgtService.lookup(any(), any(), any(), any(), any())).thenReturn(minWgt);

        CustomerStdEntity custStd = new CustomerStdEntity();
        custStd.setPkgWgtLow(new BigDecimal("13000"));
        when(customerStdService.findFirstMatch(any(), any(), any(), any())).thenReturn(custStd);

        SdSecondWgtLowAction action = new SdSecondWgtLowAction(hrMinWgtService, customerStdService);
        SDSlabEntity slab = sampleSlab(new BigDecimal("10000"));
        action.execute(sampleOrder(), slab);

        // max(10000, 12000, 13000) = 13000
        assertThat(slab.getSecondWgtLow()).isEqualByComparingTo("13000");
    }

    @Test
    void noCustomerStd_picksMaxOfTwo() {
        HrMinWgtEntity minWgt = new HrMinWgtEntity();
        minWgt.setMinWgt(new BigDecimal("12000"));
        when(hrMinWgtService.lookup(any(), any(), any(), any(), any())).thenReturn(minWgt);
        when(customerStdService.findFirstMatch(any(), any(), any(), any())).thenReturn(null);

        SdSecondWgtLowAction action = new SdSecondWgtLowAction(hrMinWgtService, customerStdService);
        SDSlabEntity slab = sampleSlab(new BigDecimal("10000"));
        action.execute(sampleOrder(), slab);

        // max(10000, 12000) = 12000
        assertThat(slab.getSecondWgtLow()).isEqualByComparingTo("12000");
    }

    @Test
    void dg106_hrMinWgtMisses_throws() {
        when(hrMinWgtService.lookup(any(), any(), any(), any(), any())).thenReturn(null);

        SdSecondWgtLowAction action = new SdSecondWgtLowAction(hrMinWgtService, customerStdService);
        SDSlabEntity slab = sampleSlab(new BigDecimal("10000"));

        assertThatThrownBy(() -> action.execute(sampleOrder(), slab))
            .isInstanceOf(AlgorithmException.class)
            .extracting("errorCode")
            .isEqualTo(SdErrorCode.ALG_HR_MIN_WGT_NOT_FOUND);
    }

    private SDOrderEntity sampleOrder() {
        SDOrderEntity o = new SDOrderEntity();
        o.setCmpCd("K");
        o.setOrgCd("K01");
        o.setOrderNo("ORD-1");
        o.setProductCd("COIL");
        o.setCustomerCd("CUST1");
        o.setConfirmedPlantCd("A1234567");
        return o;
    }

    private SDSlabEntity sampleSlab(BigDecimal firstWgtLow) {
        SDSlabEntity s = new SDSlabEntity();
        s.setSlabThickness(new BigDecimal("250"));
        s.setFirstWidthLow(new BigDecimal("1150"));
        s.setFirstWgtLow(firstWgtLow);
        return s;
    }
}
