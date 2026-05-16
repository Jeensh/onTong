package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.feature.sd.process.working.service.SlabNoSequence;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import com.example.slabdesign.store.sd.working.domain.logic.SDSlabLogic;
import com.example.slabdesign.store.sd.working.jpo.SlabResultJpo;
import com.example.slabdesign.store.sd.working.repository.SlabResultRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link SdSlabSaveAction} (step 20: SLAB_RESULT 저장).
 */
@ExtendWith(MockitoExtension.class)
class SdSlabSaveActionTest {

    @Mock SlabResultRepository repository;
    @Mock SDSlabLogic logic;
    @Mock SlabNoSequence slabNoSequence;

    @Test
    void singleSlab_savesOneRow() {
        when(logic.toJpo(any())).thenReturn(new SlabResultJpo());
        SdSlabSaveAction action = new SdSlabSaveAction(repository, logic, slabNoSequence);

        SDOrderEntity order = new SDOrderEntity();
        SDSlabEntity slab = baseSlab();
        slab.setSlabCountInProgress(1);
        slab.setSlabNo("000000000001");

        List<String> savedNos = action.execute(order, slab);

        assertThat(savedNos).containsExactly("000000000001");
        verify(repository, times(1)).save(any());
        // First slab uses the pre-set slabNo — sequence not consulted
        verify(slabNoSequence, times(0)).next();
    }

    @Test
    void multipleSlab_savesEachWithNewNo() {
        when(logic.toJpo(any())).thenReturn(new SlabResultJpo());
        when(slabNoSequence.next()).thenReturn("000000000002", "000000000003");

        SdSlabSaveAction action = new SdSlabSaveAction(repository, logic, slabNoSequence);

        SDOrderEntity order = new SDOrderEntity();
        SDSlabEntity slab = baseSlab();
        slab.setSlabCountInProgress(3);
        slab.setSlabNo("000000000001");

        List<String> savedNos = action.execute(order, slab);

        assertThat(savedNos).containsExactly("000000000001", "000000000002", "000000000003");
        verify(repository, times(3)).save(any());
    }

    @Test
    void execute_copiesAlgorithmResultsToFinalFields() {
        when(logic.toJpo(any())).thenReturn(new SlabResultJpo());
        SdSlabSaveAction action = new SdSlabSaveAction(repository, logic, slabNoSequence);

        SDOrderEntity order = new SDOrderEntity();
        SDSlabEntity slab = baseSlab();
        slab.setSlabCountInProgress(1);
        slab.setSlabNo("000000000001");

        action.execute(order, slab);

        // Original + _1 should both reflect the algorithm decisions
        assertThat(slab.getSlabWidth()).isEqualByComparingTo("1300");
        assertThat(slab.getSlabWidth1()).isEqualByComparingTo("1300");
        assertThat(slab.getSlabLength()).isEqualByComparingTo("7867");
        assertThat(slab.getSlabLength1()).isEqualByComparingTo("7867");
        assertThat(slab.getSlabWgt()).isEqualByComparingTo("20000");
        assertThat(slab.getSlabWgt1()).isEqualByComparingTo("20000");
        assertThat(slab.getSplitCount()).isEqualTo(2);
        assertThat(slab.getCreatedAt()).isNotNull();
    }

    private SDSlabEntity baseSlab() {
        SDSlabEntity s = new SDSlabEntity();
        s.setTargetSlabWidth(new BigDecimal("1300"));
        s.setFinalWidthHigh(new BigDecimal("1500"));
        s.setFinalWidthLow(new BigDecimal("1024"));
        s.setTargetSlabLength(new BigDecimal("7867"));
        s.setFinalLengthHigh(new BigDecimal("10000"));
        s.setFinalLengthLow(new BigDecimal("6000"));
        s.setSlabWgtInProgress(new BigDecimal("20000"));
        s.setSplitWgtHigh(new BigDecimal("25000"));
        s.setSplitWgtLow(new BigDecimal("13000"));
        s.setOptimalSplitCount(2);
        return s;
    }
}
