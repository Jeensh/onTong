package com.example.slabdesign.feature.sd.process.std.service;

import com.example.slabdesign.store.sd.std.domain.entity.HrSpecEntity;
import com.example.slabdesign.store.sd.std.domain.logic.HrSpecLogic;
import com.example.slabdesign.store.sd.std.jpo.HrSpecPK;
import com.example.slabdesign.store.sd.std.repository.HrSpecRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

/**
 * sd · std · HR_SPEC 룩업 서비스.
 * 4-축 composite key (온톨로지/소/열연공장/품종) 정확매칭 룩업.
 */
@Service
public class HrSpecService {

    private final HrSpecRepository repository;
    private final HrSpecLogic logic;

    @Autowired
    public HrSpecService(HrSpecRepository repository, HrSpecLogic logic) {
        this.repository = repository;
        this.logic = logic;
    }

    public HrSpecEntity lookup(String cmpCd, String orgCd, String hrPlantCd, String productCd) {
        HrSpecPK pk = new HrSpecPK(cmpCd, orgCd, hrPlantCd, productCd);
        return repository.findById(pk).map(logic::toEntity).orElse(null);
    }
}
