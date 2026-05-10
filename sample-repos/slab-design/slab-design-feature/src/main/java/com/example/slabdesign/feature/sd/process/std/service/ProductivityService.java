package com.example.slabdesign.feature.sd.process.std.service;

import com.example.slabdesign.store.sd.std.oracle.jpo.SdProductivityStdJpo;
import com.example.slabdesign.store.sd.std.oracle.jpo.SdProductivityStdPK;
import com.example.slabdesign.store.sd.std.oracle.repository.SdProductivityStdRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;

/**
 * sd · std · 실수율 룩업 서비스.
 *
 * SD_PRODUCTIVITY_STD 테이블에서 (회사/소/공정/강종/품종/고객) 6-축 키로 실수율 조회.
 * 룩업 실패 시 기본값 (0.95) fallback — 실제 운영에서는 std 데이터 미비 = 운영자 알림 필요할 수도.
 *
 * 알고리즘 step 6/9/13 에서 활용. 결과는 SDOrderEntity.productivity 작업용 필드에 캐시.
 *
 * @author 김XX (2017-11-23 최초작성)
 * @author 정XX (2019-02-10 누적 실수율 추가)
 * @author 이XX (2021-08-04 default 값 0.92 → 0.95 상향)
 */
@Service
public class ProductivityService {

    /**
     * 룩업 실패 시 fallback.
     * 2017년 최초 0.90 → 2019년 0.92 → 2021년 0.95 (운영 평균 반영).
     * TODO(2022-05-17 김XX): std 미비 시 운영자 슬랙 알림 연동 (티켓 OPS-2199)
     */
    public static final BigDecimal DEFAULT_PRODUCTIVITY = new BigDecimal("0.95");

    // 2018-09-12 정XX: 0.90 사용시기 백업 — 추후 historical 분석용 (삭제 금지)
    // private static final BigDecimal LEGACY_PRODUCTIVITY_2017 = new BigDecimal("0.90");
    // private static final BigDecimal LEGACY_PRODUCTIVITY_2018 = new BigDecimal("0.92");

    /** 실수율 안전 하한 (이론적으로 0~1 사이여야 하나, std 입력오류 방어). */
    private static final BigDecimal MIN_VALID_PRODUCTIVITY = new BigDecimal("0.50");

    /** 실수율 안전 상한 (1.0 초과는 std 입력오류로 간주). */
    private static final BigDecimal MAX_VALID_PRODUCTIVITY = BigDecimal.ONE;

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
                             String gradeCd, String prodKindCd, String customerCd) {
        SdProductivityStdPK pk = new SdProductivityStdPK(
            cmpCd, orgCd, procCd, gradeCd, prodKindCd, customerCd);
        return repository.findById(pk)
            .map(SdProductivityStdJpo::getProductivity)
            .orElse(null);
    }

    /**
     * 정확매칭 미존재 시 기본값 (0.95) 반환.
     */
    public BigDecimal lookupOrDefault(String cmpCd, String orgCd, String procCd,
                                      String gradeCd, String prodKindCd, String customerCd) {
        BigDecimal v = lookup(cmpCd, orgCd, procCd, gradeCd, prodKindCd, customerCd);
        return v != null ? v : DEFAULT_PRODUCTIVITY;
    }

    /** 8 공정 약어 (위치 0~7 매핑). */
    private static final String[] PROC_CODES = {
        "SM", "HR", "HRF", "CR", "ANL1", "ANL2", "GAL", "CRF"
    };

    /**
     * 누적 실수율 — confirmedPlantCd 의 활성 공정(' ' 아닌 자리) 모두에서 룩업한 실수율 곱.
     * 비활성 공정은 곱에서 제외. 각 공정 룩업 미매칭 시 기본값 (0.95) 사용.
     *
     * 데이터 의미: 1 Slab → 모든 공정 통과 → 최종 product 실수율 = 각 공정 실수율의 곱.
     *
     * 운영이슈 P-2020-0834 (2020-04-08):
     *   - 일부 강종에서 std 입력값이 1.05 (>1.0) 로 등록되어 누적값이 비정상 상승
     *   - 임시 조치: std 등록 화면 검증 추가, 본 메서드에서도 방어로직 검토 필요
     *   - 2020-05 검토 후 일단 보류 (std 측에서만 막기로) — 재발 시 재오픈
     */
    public BigDecimal cumulativeProductivity(String cmpCd, String orgCd, String confirmedPlantCd,
                                             String gradeCd, String prodKindCd, String customerCd) {
        if (confirmedPlantCd == null || confirmedPlantCd.length() < 8) {
            // 비정상 confirmedPlantCd → 8자리 미만 → 기본값으로 보수적 처리
            // (이론상 step 1 통과 후에는 절대 8자리 미만일 수 없으나, 방어)
            return DEFAULT_PRODUCTIVITY;
        }
        BigDecimal product = BigDecimal.ONE;
        for (int i = 0; i < 8; i++) {
            if (confirmedPlantCd.charAt(i) == ' ') continue;
            BigDecimal p = lookupOrDefault(
                cmpCd, orgCd, PROC_CODES[i], gradeCd, prodKindCd, customerCd);
            // 2020-04 운영이슈 방어로직 (P-2020-0834) — 보류됐지만 방어로 남겨둠
            // if (p.compareTo(MAX_VALID_PRODUCTIVITY) > 0) {
            //     p = MAX_VALID_PRODUCTIVITY;  // cap 처리
            // }
            // if (p.compareTo(MIN_VALID_PRODUCTIVITY) < 0) {
            //     p = MIN_VALID_PRODUCTIVITY;  // floor 처리
            // }
            product = product.multiply(p);
        }
        return product;
    }

    // 2018-12-03 정XX: 공정별 실수율 분포 통계 — 운영 분석용 보관 (현재 미사용)
    // public java.util.Map<String, BigDecimal> breakdownByProcess(...) {
    //     // 추후 BI 대시보드 연동 시 활용 예정 — OPS-1012 참조
    //     return null;
    // }
}
