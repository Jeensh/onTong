package com.example.slabdesign.store.sd.working.oracle.repository;

import com.example.slabdesign.store.sd.working.oracle.jpo.SDOrderChemicalJpo;
import com.example.slabdesign.store.sd.working.oracle.jpo.SDOrderPK;
import org.springframework.data.jpa.repository.JpaRepository;

/**
 * sd · working · ORDER_CHEMICAL JPA repository.
 */
public interface SDOrderChemicalRepository extends JpaRepository<SDOrderChemicalJpo, SDOrderPK> {
    // 21-step 알고리즘에서 직접 참조 안 됨 — 시나리오 확장 시 추가
}
