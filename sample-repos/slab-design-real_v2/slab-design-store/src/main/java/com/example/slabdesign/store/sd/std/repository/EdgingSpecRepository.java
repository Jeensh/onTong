package com.example.slabdesign.store.sd.std.repository;

import com.example.slabdesign.store.sd.std.jpo.EdgingSpecJpo;
import com.example.slabdesign.store.sd.std.jpo.EdgingSpecPK;
import org.springframework.data.jpa.repository.JpaRepository;

/**
 * sd · std · EDGING_SPEC repository.
 * P2.2: 정확매칭(EDGING_GROUP_CD = ?) → 미존재 시 '*' fallback (application logic).
 */
public interface EdgingSpecRepository extends JpaRepository<EdgingSpecJpo, EdgingSpecPK> {
}
