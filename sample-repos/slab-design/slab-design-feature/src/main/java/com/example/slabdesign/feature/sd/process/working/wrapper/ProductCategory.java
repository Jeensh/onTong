package com.example.slabdesign.feature.sd.process.working.wrapper;

/**
 * Slab 설계 대상 제품 분류.
 *
 * 데모 알고리즘은 COIL 만 처리. PLATE / UNKNOWN 은 알고리즘 진입 차단.
 * 향후 시나리오 확장 시 PLATE 알고리즘 추가 가능 — 드라마 DNA "조건분기 파골" 시드.
 */
public enum ProductCategory {
    /** Coil — 데모 알고리즘 처리 대상. */
    COIL,
    /** 외판(Plate) — 데모는 분기만 두고 미구현. */
    PLATE,
    /** 분류 불가 (NULL 또는 형식 오류). */
    UNKNOWN
}
