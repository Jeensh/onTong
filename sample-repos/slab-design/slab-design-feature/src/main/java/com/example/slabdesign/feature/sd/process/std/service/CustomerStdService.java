package com.example.slabdesign.feature.sd.process.std.service;

import com.example.slabdesign.store.sd.std.domain.entity.CustomerStdEntity;
import com.example.slabdesign.store.sd.std.domain.logic.CustomerStdLogic;
import com.example.slabdesign.store.sd.std.oracle.jpo.CustomerStdJpo;
import com.example.slabdesign.store.sd.std.oracle.repository.CustomerStdRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * sd · std · CUSTOMER_STD 룩업 서비스.
 *
 * 매칭 조건: (회사, 소, 품명, 고객사) — PRIORITY ASC, 첫 row.
 * 미매칭 시 null 반환 (제한 없음 — 사용자 사양).
 */
@Service
public class CustomerStdService {

    private final CustomerStdRepository repository;
    private final CustomerStdLogic logic;

    @Autowired
    public CustomerStdService(CustomerStdRepository repository, CustomerStdLogic logic) {
        this.repository = repository;
        this.logic = logic;
    }

    public CustomerStdEntity findFirstMatch(String cmpCd, String orgCd,
                                            String productNameCd, String customerCd) {
        List<CustomerStdJpo> matches = repository
            .findByCmpCdAndOrgCdAndProductNameCdAndCustomerCdOrderByPriorityAsc(
                cmpCd, orgCd, productNameCd, customerCd);
        if (matches.isEmpty()) return null;
        return logic.toEntity(matches.get(0));
    }
}
