package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.feature.sd.process.working.wrapper.ProductCategory;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import org.springframework.stereotype.Component;

/**
 * sd · working · 제품 분류기.
 *
 * 도메인 룰: 품명(PRODUCT_CD)의 앞 2글자(=품종) 로 분류.
 *   - 'FS' → 외판(PLATE)
 *   - 그 외 → COIL
 *   - NULL/형식오류 → UNKNOWN
 *
 * 데모 알고리즘은 COIL 만 처리 — 호출자가 분류 결과로 알고리즘 진입 분기.
 *
 * 시나리오 확장 후보 (P3):
 *   - PLATE 알고리즘 추가 시 분기 활성화
 *   - 새 품종 코드 추가 시 도메인 룰 변경 → 어느 주문 영향? 데모
 */
@Component
public class SdProductClassifier {

    public ProductCategory classify(SDOrderEntity order) {
        if (order == null) return ProductCategory.UNKNOWN;
        return classifyByProductCode(order.getProductCd());
    }

    /**
     * 품명 코드 (3글자) 의 앞 2글자(=품종) 로 분류.
     */
    public ProductCategory classifyByProductCode(String productCode) {
        if (productCode == null || productCode.length() < 2) {
            return ProductCategory.UNKNOWN;
        }
        String prefix2 = productCode.substring(0, 2).toUpperCase();
        if ("FS".equals(prefix2)) {
            return ProductCategory.PLATE;
        }
        // 그 외 모두 COIL — 데모는 이 분기만 알고리즘 진입
        return ProductCategory.COIL;
    }

    /** 데모 알고리즘 진입 가능 여부 = COIL 만 true. */
    public boolean isDesignableInDemo(SDOrderEntity order) {
        return classify(order) == ProductCategory.COIL;
    }
}
