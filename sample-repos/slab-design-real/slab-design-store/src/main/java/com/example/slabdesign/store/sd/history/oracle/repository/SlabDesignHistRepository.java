package com.example.slabdesign.store.sd.history.oracle.repository;

import com.example.slabdesign.store.sd.history.oracle.jpo.SlabDesignHistJpo;
import com.example.slabdesign.store.sd.history.oracle.jpo.SlabDesignHistPK;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

/**
 * sd · history · SLAB_DESIGN_HIST repository.
 * P2.4: step 별 적재 + 주문/슬랩 별 조회.
 */
public interface SlabDesignHistRepository extends JpaRepository<SlabDesignHistJpo, SlabDesignHistPK> {

    /** 주문 기준 모든 이력 (실패 포함). EventTime 오름차순. */
    List<SlabDesignHistJpo> findByCmpCdAndOrgCdAndOrderNoOrderByEventTimeAsc(
        String cmpCd, String orgCd, String orderNo);

    /** 특정 슬랩 기준 이력 (성공 케이스). */
    List<SlabDesignHistJpo> findByCmpCdAndOrgCdAndSlabNoOrderByStepNoAsc(
        String cmpCd, String orgCd, String slabNo);
}
