package com.example.slabdesign.store.sd.std.oracle.repository;

import com.example.slabdesign.store.sd.std.oracle.jpo.HrMinWgtJpo;
import com.example.slabdesign.store.sd.std.oracle.jpo.HrMinWgtPK;
import org.springframework.data.jpa.repository.JpaRepository;

import java.math.BigDecimal;
import java.util.Optional;

/**
 * sd · std · HR_MIN_WGT repository (2차원 sheet 룩업).
 * HR_MAX_WGT 와 동일한 룩업 패턴 (사용자 사양).
 */
public interface HrMinWgtRepository extends JpaRepository<HrMinWgtJpo, HrMinWgtPK> {

    Optional<HrMinWgtJpo> findFirstByCmpCdAndOrgCdAndHrCdAndThicknessGreaterThanEqualAndWidthGreaterThanEqualOrderByThicknessAscWidthAsc(
        String cmpCd, String orgCd, String hrCd,
        BigDecimal thickness, BigDecimal width
    );
}
