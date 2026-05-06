package com.example.slabdesign.store.sd.std.oracle.repository;

import com.example.slabdesign.store.sd.std.oracle.jpo.CustomerStdJpo;
import com.example.slabdesign.store.sd.std.oracle.jpo.CustomerStdPK;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

/**
 * sd · std · CUSTOMER_STD repository.
 *
 * P2.2 step 5/6: 매칭 검색 — 품명/고객사 조건 일치 row 들을 PRIORITY 순서로 조회.
 * (EDGING_GROUP 과 동일한 우선순위 기반 매칭 패턴)
 */
public interface CustomerStdRepository extends JpaRepository<CustomerStdJpo, CustomerStdPK> {

    /**
     * 매칭 조회. PRIORITY 오름차순 정렬.
     */
    List<CustomerStdJpo> findByCmpCdAndOrgCdAndProductNameCdAndCustomerCdOrderByPriorityAsc(
        String cmpCd, String orgCd, String productNameCd, String customerCd
    );
}
