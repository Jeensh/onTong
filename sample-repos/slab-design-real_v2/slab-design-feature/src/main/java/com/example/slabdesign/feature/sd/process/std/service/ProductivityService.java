package com.example.slabdesign.feature.sd.process.std.service;

import com.example.slabdesign.feature.sd.common.SdConstants;
import com.example.slabdesign.store.sd.std.jpo.SdProductivityStdJpo;
import com.example.slabdesign.store.sd.std.jpo.SdProductivityStdPK;
import com.example.slabdesign.store.sd.std.repository.SdProductivityStdRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;

/**
 * sd · std · 실수율 룩업 서비스.
 *
 * SD_PRODUCTIVITY_STD 테이블에서 (회사/소/공정/강종/품종/고객) 6-축 키로 실수율 조회.
 * 룩업 실패 시 SdConstants.DEFAULT_PRODUCTIVITY fallback.
 *
 * 알고리즘 step 6/9/13 에서 활용. 결과는 SDOrderEntity.productivity 작업용 필드에 캐시.
 */
@Service
public class ProductivityService {

    /** 룩업 실패 시 fallback. */
    public static final BigDecimal DEFAULT_PRODUCTIVITY =
        BigDecimal.valueOf(SdConstants.DEFAULT_PRODUCTIVITY);

    private final SdProductivityStdRepository repository;

    @Autowired
    public ProductivityService(SdProductivityStdRepository repository) {
        this.repository = repository;
    }

    /**
     * 실수율 정확매칭 룩업.
     * @return 매칭된 실수율 또는 null (미매칭 시).
     */
    public BigDecimal lookup(String cmpCd, String orgCd, String procCd,
                             String gradeCd, String productCd, String customerCd) {
        SdProductivityStdPK pk = new SdProductivityStdPK(
            cmpCd, orgCd, procCd, gradeCd, productCd, customerCd);
        return repository.findById(pk)
            .map(SdProductivityStdJpo::getProductivity)
            .orElse(null);
    }

    /**
     * 정확매칭 미존재 시 기본값 반환.
     */
    public BigDecimal lookupOrDefault(String cmpCd, String orgCd, String procCd,
                                      String gradeCd, String productCd, String customerCd) {
        BigDecimal v = lookup(cmpCd, orgCd, procCd, gradeCd, productCd, customerCd);
        return v != null ? v : DEFAULT_PRODUCTIVITY;
    }

    /**
     * 누적 실수율 — confirmedPlantCd 의 활성 공정(' ' 아닌 자리) 모두에서 룩업한 실수율 곱.
     * 비활성 공정은 곱에서 제외. 각 공정 룩업 미매칭 시 기본값 사용.
     *
     * 데이터 의미: 1 슬랩 → 모든 공정 통과 → 최종 product 실수율 = 각 공정 실수율의 곱.
     */
    public BigDecimal cumulativeProductivity(String cmpCd, String orgCd, String confirmedPlantCd,
                                             String gradeCd, String productCd, String customerCd) {
        if (confirmedPlantCd == null || confirmedPlantCd.length() < SdConstants.CONFIRMED_PLANT_CD_LENGTH) {
            // 비정상 confirmedPlantCd → 8자리 미만 → 기본값으로 보수적 처리
            return DEFAULT_PRODUCTIVITY;
        }
        BigDecimal product = BigDecimal.ONE;
        for (int i = 0; i < SdConstants.CONFIRMED_PLANT_CD_LENGTH; i++) {
            if (confirmedPlantCd.charAt(i) == SdConstants.INACTIVE_PROCESS) continue;
            BigDecimal p = lookupOrDefault(
                cmpCd, orgCd, SdConstants.PROC_CODES[i], gradeCd, productCd, customerCd);
            product = product.multiply(p);
        }
        return product;
    }
}
