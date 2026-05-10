package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.logic.SDOrderLogic;
import com.example.slabdesign.store.sd.working.jpo.SDOrderOsJpo;
import com.example.slabdesign.store.sd.working.jpo.SDOrderPK;
import com.example.slabdesign.store.sd.working.repository.SDOrderChemicalRepository;
import com.example.slabdesign.store.sd.working.repository.SDOrderOmRepository;
import com.example.slabdesign.store.sd.working.repository.SDOrderOsRepository;
import com.example.slabdesign.store.sd.working.repository.SDOrderQdRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Collections;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link SdOrderExtractor}.
 *
 * Verifies orchestration: OS findDesignable → OM/QD/CHEMICAL findById → Logic.toEntity.
 */
@ExtendWith(MockitoExtension.class)
class SdOrderExtractorTest {

    @Mock SDOrderOsRepository osRepository;
    @Mock SDOrderOmRepository omRepository;
    @Mock SDOrderQdRepository qdRepository;
    @Mock SDOrderChemicalRepository chemicalRepository;
    @Mock SDOrderLogic orderLogic;

    @Test
    void emptyOsList_returnsEmptyList() {
        when(osRepository.findDesignable("K", "K01")).thenReturn(Collections.emptyList());

        SdOrderExtractor extractor = new SdOrderExtractor(
            osRepository, omRepository, qdRepository, chemicalRepository, orderLogic);
        List<SDOrderEntity> result = extractor.extractDesignableOrders("K", "K01");

        assertThat(result).isEmpty();
    }

    @Test
    void singleOsRow_resolvesAllJpos() {
        SDOrderOsJpo os = new SDOrderOsJpo();
        os.setCmpCd("K");
        os.setOrgCd("K01");
        os.setOrderNo("ORD-1");
        when(osRepository.findDesignable("K", "K01")).thenReturn(List.of(os));
        when(omRepository.findById(any(SDOrderPK.class))).thenReturn(Optional.empty());
        when(qdRepository.findById(any(SDOrderPK.class))).thenReturn(Optional.empty());
        when(chemicalRepository.findById(any(SDOrderPK.class))).thenReturn(Optional.empty());
        SDOrderEntity entity = new SDOrderEntity();
        entity.setOrderNo("ORD-1");
        when(orderLogic.toEntity(any(), any(), any(), any())).thenReturn(entity);

        SdOrderExtractor extractor = new SdOrderExtractor(
            osRepository, omRepository, qdRepository, chemicalRepository, orderLogic);
        List<SDOrderEntity> result = extractor.extractDesignableOrders("K", "K01");

        assertThat(result).hasSize(1);
        assertThat(result.get(0).getOrderNo()).isEqualTo("ORD-1");
    }
}
