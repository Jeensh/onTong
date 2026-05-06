package com.example.slabdesign.store.sd.std.oracle.repository;

import com.example.slabdesign.store.sd.std.oracle.jpo.SdProductivityStdJpo;
import com.example.slabdesign.store.sd.std.oracle.jpo.SdProductivityStdPK;
import org.springframework.data.jpa.repository.JpaRepository;

/**
 * sd · std · SD_PRODUCTIVITY_STD repository.
 * P2.2 step 6/9/13: findById(SdProductivityStdPK) — 정확매칭으로 실수율 조회.
 */
public interface SdProductivityStdRepository extends JpaRepository<SdProductivityStdJpo, SdProductivityStdPK> {
}
