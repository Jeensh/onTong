package com.example.slabdesign.feature.sd.process.std.service;

import com.example.slabdesign.store.sd.std.domain.entity.CastSpecEntity;
import com.example.slabdesign.store.sd.std.domain.logic.CastSpecLogic;
import com.example.slabdesign.store.sd.std.jpo.CastSpecPK;
import com.example.slabdesign.store.sd.std.repository.CastSpecRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

/**
 * sd · std · CAST_SPEC 룩업 서비스.
 * 6-축 composite key (온톨로지/소/제강/연주/머신/품종) 정확매칭 룩업.
 */
@Service
public class CastSpecService {

    private final CastSpecRepository repository;
    private final CastSpecLogic logic;

    @Autowired
    public CastSpecService(CastSpecRepository repository, CastSpecLogic logic) {
        this.repository = repository;
        this.logic = logic;
    }

    public CastSpecEntity lookup(String cmpCd, String orgCd, String smCd,
                                  String castCd, String machineCd, String productCd) {
        CastSpecPK pk = new CastSpecPK(cmpCd, orgCd, smCd, castCd, machineCd, productCd);
        return repository.findById(pk).map(logic::toEntity).orElse(null);
    }
}
