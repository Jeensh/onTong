package com.example.slabdesign.store.sd.std.oracle.repository;

import com.example.slabdesign.store.sd.std.oracle.jpo.EdgingGroupJpo;
import com.example.slabdesign.store.sd.std.oracle.jpo.EdgingGroupPK;
import org.springframework.data.jpa.repository.JpaRepository;

import java.math.BigDecimal;
import java.util.List;

/**
 * sd · std · EDGING_GROUP repository.
 *
 * P2.2 step 2: 강종/품종/고객사/열연목표폭 으로 매칭되는 row 들을 우선순위 순으로 조회.
 * 매칭 조건:
 *   GRADE_CD = ? AND PRODUCT_TYPE_CD = ? AND CUSTOMER_CD = ?
 *   AND HR_TGT_WIDTH_LOW <= ? AND HR_TGT_WIDTH_HIGH >= ?
 * ORDER BY PRIORITY ASC (또는 DESC — 사용자 룰에 따라)
 */
public interface EdgingGroupRepository extends JpaRepository<EdgingGroupJpo, EdgingGroupPK> {

    /**
     * 매칭 조회 (P2.2 에서 활용). PRIORITY 오름차순으로 정렬.
     */
    List<EdgingGroupJpo> findByCmpCdAndOrgCdAndGradeCdAndProductTypeCdAndCustomerCdAndHrTgtWidthLowLessThanEqualAndHrTgtWidthHighGreaterThanEqualOrderByPriorityAsc(
        String cmpCd, String orgCd, String gradeCd, String productTypeCd, String customerCd,
        BigDecimal hrTgtWidth, BigDecimal hrTgtWidthHigh
    );
}
