package com.example.slabdesign.feature.sd.process.std.service;

import com.example.slabdesign.feature.sd.common.SdConstants;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;

/**
 * sd · std · 비중(specific gravity) 제공.
 *
 * 데모는 SdConstants.DEFAULT_SPECIFIC_GRAVITY 상수 고정. 실제 운영은 std 테이블 룩업 가능.
 *
 * 알고리즘 step 4/16~19 에서 단중·치수 변환 시 사용. 결과는 SDOrderEntity.specificGravity 캐시.
 */
@Service
public class SpecificGravityProvider {

    public static final BigDecimal DEFAULT_GRAVITY =
        BigDecimal.valueOf(SdConstants.DEFAULT_SPECIFIC_GRAVITY);

    /** 비중 반환. 데모는 상수, 향후 강종별 분기 가능. */
    public BigDecimal get() {
        return DEFAULT_GRAVITY;
    }

    /** 강종별 비중 (현재는 모두 동일, 시나리오 확장용). */
    public BigDecimal get(String gradeCd) {
        return DEFAULT_GRAVITY;
    }
}
