package com.example.slabdesign.store.sd.working.repository;

import com.example.slabdesign.store.sd.working.jpo.SlabResultJpo;
import com.example.slabdesign.store.sd.working.jpo.SlabResultPK;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

/**
 * sd · working · SLAB_RESULT repository.
 * P2.4: 결과 저장 + 주문번호별 조회.
 */
public interface SlabResultRepository extends JpaRepository<SlabResultJpo, SlabResultPK> {

    /** 주문번호 기준 모든 slab 조회 (1 주문 → N Slab). */
    List<SlabResultJpo> findByCmpCdAndOrgCdAndOrderNo(String cmpCd, String orgCd, String orderNo);

    /** Slab 번호 단건 조회 (온톨로지·소를 모르는 검색 시나리오). */
    Optional<SlabResultJpo> findFirstBySlabNo(String slabNo);
}
