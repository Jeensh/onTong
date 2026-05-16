package com.example.slabdesign.store.sd.std.repository;

import com.example.slabdesign.store.sd.std.jpo.CastSpecJpo;
import com.example.slabdesign.store.sd.std.jpo.CastSpecPK;
import org.springframework.data.jpa.repository.JpaRepository;

/**
 * sd · std · CAST_SPEC repository.
 * P2.2 step 1: findById(CastSpecPK) — 정확매칭으로 두께·폭·길이 기준 조회.
 */
public interface CastSpecRepository extends JpaRepository<CastSpecJpo, CastSpecPK> {
}
