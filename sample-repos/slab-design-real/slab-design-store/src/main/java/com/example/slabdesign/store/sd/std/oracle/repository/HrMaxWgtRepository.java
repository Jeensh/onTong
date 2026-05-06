package com.example.slabdesign.store.sd.std.oracle.repository;

import com.example.slabdesign.store.sd.std.oracle.jpo.HrMaxWgtJpo;
import com.example.slabdesign.store.sd.std.oracle.jpo.HrMaxWgtPK;
import org.springframework.data.jpa.repository.JpaRepository;

import java.math.BigDecimal;
import java.util.Optional;

/**
 * sd · std · HR_MAX_WGT repository (2차원 sheet 룩업).
 *
 * 룩업: 입력 (두께, 폭) → cell.두께 >= 입력두께 AND cell.폭 >= 입력폭 인 row 들 중
 *       (두께 ASC, 폭 ASC) 정렬 후 첫 1건. 즉 입력값을 cover 하는 가장 작은 cell.
 */
public interface HrMaxWgtRepository extends JpaRepository<HrMaxWgtJpo, HrMaxWgtPK> {

    Optional<HrMaxWgtJpo> findFirstByCmpCdAndOrgCdAndHrCdAndThicknessGreaterThanEqualAndWidthGreaterThanEqualOrderByThicknessAscWidthAsc(
        String cmpCd, String orgCd, String hrCd,
        BigDecimal thickness, BigDecimal width
    );
}
