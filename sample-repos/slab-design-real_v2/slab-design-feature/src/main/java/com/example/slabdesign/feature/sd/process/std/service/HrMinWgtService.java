package com.example.slabdesign.feature.sd.process.std.service;

import com.example.slabdesign.store.sd.std.domain.entity.HrMinWgtEntity;
import com.example.slabdesign.store.sd.std.domain.logic.HrMinWgtLogic;
import com.example.slabdesign.store.sd.std.repository.HrMinWgtRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;

/**
 * sd · std · HR_MIN_WGT 2차원 sheet 룩업.
 *
 * 룩업 패턴: cell.thickness ≥ input.thickness AND cell.width ≥ input.width
 *           ORDER BY thickness ASC, width ASC LIMIT 1
 *           = 입력값을 cover 하는 가장 작은 cell 의 MIN_WGT 반환.
 *
 * 미매칭 시 null. 호출자가 fail 처리 (DG106).
 */
@Service
public class HrMinWgtService {

    private final HrMinWgtRepository repository;
    private final HrMinWgtLogic logic;

    @Autowired
    public HrMinWgtService(HrMinWgtRepository repository, HrMinWgtLogic logic) {
        this.repository = repository;
        this.logic = logic;
    }

    public HrMinWgtEntity lookup(String cmpCd, String orgCd, String hrCd,
                                  BigDecimal thickness, BigDecimal width) {
        return repository
            .findFirstByCmpCdAndOrgCdAndHrCdAndThicknessGreaterThanEqualAndWidthGreaterThanEqualOrderByThicknessAscWidthAsc(
                cmpCd, orgCd, hrCd, thickness, width)
            .map(logic::toEntity)
            .orElse(null);
    }
}
