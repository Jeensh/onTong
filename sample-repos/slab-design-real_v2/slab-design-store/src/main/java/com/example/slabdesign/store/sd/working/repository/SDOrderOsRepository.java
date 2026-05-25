package com.example.slabdesign.store.sd.working.repository;

import com.example.slabdesign.store.sd.working.jpo.SDOrderOsJpo;
import com.example.slabdesign.store.sd.working.jpo.SDOrderPK;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;

/**
 * sd · working · ORDER_OS JPA repository.
 * Composite PK: SDOrderPK (cmpCd, orgCd, orderNo).
 * feature 직접 호출 금지 — SDOrderLogic 경유.
 */
public interface SDOrderOsRepository extends JpaRepository<SDOrderOsJpo, SDOrderPK> {

    /**
     * P2.1 Phase 1 — 설계 대상 후보 주문 추출.
     * 필터:
     *   진도 IN ('C', 'D')  AND
     *   (종결 플래그 IS NULL OR NOT IN (1, 2))   -- 1:종결, 2:보류 제외, NULL/0 통과
     */
    @Query("""
        SELECT o FROM SDOrderOsJpo o
        WHERE o.cmpCd = :cmpCd
          AND o.orgCd = :orgCd
          AND o.osProgress IN ('C', 'D')
          AND (o.closeFlag IS NULL OR o.closeFlag NOT IN (1, 2))
        """)
    List<SDOrderOsJpo> findDesignable(@Param("cmpCd") String cmpCd,
                                      @Param("orgCd") String orgCd);

    /** 온톨로지·소 단위 페이지 단위 주문 목록 (REST 브라우징용). */
    List<SDOrderOsJpo> findByCmpCdAndOrgCd(String cmpCd, String orgCd, Pageable pageable);
}
