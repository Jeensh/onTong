package com.example.slabdesign.store.sd.working.repository;

import com.example.slabdesign.store.sd.working.jpo.SDOrderPK;
import com.example.slabdesign.store.sd.working.jpo.SDOrderQdJpo;
import org.springframework.data.jpa.repository.JpaRepository;

/**
 * sd · working · ORDER_QD JPA repository.
 */
public interface SDOrderQdRepository extends JpaRepository<SDOrderQdJpo, SDOrderPK> {
    // P2.2: GRADE_CD 기반 검색
}
