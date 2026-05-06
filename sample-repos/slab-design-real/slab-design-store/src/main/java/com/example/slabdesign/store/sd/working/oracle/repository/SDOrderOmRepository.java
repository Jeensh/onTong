package com.example.slabdesign.store.sd.working.oracle.repository;

import com.example.slabdesign.store.sd.working.oracle.jpo.SDOrderOmJpo;
import com.example.slabdesign.store.sd.working.oracle.jpo.SDOrderPK;
import org.springframework.data.jpa.repository.JpaRepository;

/**
 * sd · working · ORDER_OM JPA repository.
 */
public interface SDOrderOmRepository extends JpaRepository<SDOrderOmJpo, SDOrderPK> {
    // P2.1: PRODUCT_TYPE_CD 기반 Coil 필터, 정합성 점검 검색
}
