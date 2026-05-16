package com.example.slabdesign.store.sd.std.repository;

import com.example.slabdesign.store.sd.std.jpo.HrSpecJpo;
import com.example.slabdesign.store.sd.std.jpo.HrSpecPK;
import org.springframework.data.jpa.repository.JpaRepository;

/**
 * sd · std · HR_SPEC repository.
 * P2.2 step 2/3: findById(HrSpecPK) — 정확매칭으로 폭·길이 기준 조회.
 */
public interface HrSpecRepository extends JpaRepository<HrSpecJpo, HrSpecPK> {
}
