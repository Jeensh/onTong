package com.example.slabdesign.feature.sd.process.std.service;

import com.example.slabdesign.store.sd.std.domain.entity.HrMaxWgtEntity;
import com.example.slabdesign.store.sd.std.domain.logic.HrMaxWgtLogic;
import com.example.slabdesign.store.sd.std.oracle.repository.HrMaxWgtRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;

/**
 * sd · std · HR_MAX_WGT 2차원 sheet 룩업.
 * HrMinWgtService 와 동일한 패턴. 미매칭 시 null. 호출자가 fail 처리 (DG107).
 */
@Service
public class HrMaxWgtService {

    private final HrMaxWgtRepository repository;
    private final HrMaxWgtLogic logic;

    @Autowired
    public HrMaxWgtService(HrMaxWgtRepository repository, HrMaxWgtLogic logic) {
        this.repository = repository;
        this.logic = logic;
    }

    public HrMaxWgtEntity lookup(String cmpCd, String orgCd, String hrCd,
                                  BigDecimal thickness, BigDecimal width) {
        return repository
            .findFirstByCmpCdAndOrgCdAndHrCdAndThicknessGreaterThanEqualAndWidthGreaterThanEqualOrderByThicknessAscWidthAsc(
                cmpCd, orgCd, hrCd, thickness, width)
            .map(logic::toEntity)
            .orElse(null);
    }
}
