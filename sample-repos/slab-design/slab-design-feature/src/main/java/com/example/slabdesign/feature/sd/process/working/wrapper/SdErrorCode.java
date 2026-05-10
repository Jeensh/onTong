package com.example.slabdesign.feature.sd.process.working.wrapper;

/**
 * sd 도메인 에러코드 상수.
 * DG001 ~ DG005: Phase 1 정합성 점검 (Validator).
 * DG101 ~     : Phase 2 알고리즘 단계.
 */
public final class SdErrorCode {

    private SdErrorCode() {}

    // ==== Phase 1 정합성 점검 (DG001 ~ DG005) ====
    /** 재고주문 — STOCK_CODE = 1, 새 Slab 설계 대상 아님. */
    public static final String VAL_STOCK_ORDER       = "DG001";
    /** 주문 폭/길이 양수 아님. */
    public static final String VAL_ORDER_SIZE        = "DG002";
    /** 포장 단중 범위 정합성 위반 (NULL/음수/하한>상한). */
    public static final String VAL_PKG_WGT_RANGE     = "DG003";
    /** 설계대기량 양수 위반 또는 상한 < 포장단중 하한. */
    public static final String VAL_DESIGN_PEND_QTY   = "DG004";
    /** 작업기한일 미설정 또는 과거 날짜. */
    public static final String VAL_WORK_DUE          = "DG005";

    // ==== Phase 2 알고리즘 단계 (DG101 ~) ====
    /** CAST_SPEC 매칭 실패 — step 1 두께 결정 불가. */
    public static final String ALG_CAST_SPEC_NOT_FOUND    = "DG101";
    /** HR_SPEC 매칭 실패 — step 2/3 폭/길이 범위 산정 불가. */
    public static final String ALG_HR_SPEC_NOT_FOUND      = "DG102";
    /** EDGING_GROUP 매칭 실패 — step 2 폭 범위 산정 불가. */
    public static final String ALG_EDGING_GROUP_NOT_FOUND = "DG103";
    /** 산정된 폭 범위 invalid (하한 > 상한). */
    public static final String ALG_INVALID_WIDTH_RANGE    = "DG104";
    /** 산정된 길이 범위 invalid (하한 > 상한). */
    public static final String ALG_INVALID_LENGTH_RANGE   = "DG105";
    /** HR_MIN_WGT 매칭 실패 — step 5 2차 단중 하한 산정 불가. */
    public static final String ALG_HR_MIN_WGT_NOT_FOUND   = "DG106";
    /** HR_MAX_WGT 매칭 실패 — step 6 2차 단중 상한 산정 불가. */
    public static final String ALG_HR_MAX_WGT_NOT_FOUND   = "DG107";
    /** A-a 루프 control signal — 현재 분할수 iteration 실패, 다음 split 또는 외부 fallback 필요.
     *  history 적재 대상이 아님 (loop 내부 신호). 최종 fail 은 DG109. */
    public static final String ALG_ITERATION_NEEDED       = "DG108";
    /** A-a 루프 분할수 1까지 모두 시도해도 수렴 실패 — Slab 설계 최종 불가 (Q2 답변 반영). */
    public static final String ALG_NO_CONVERGENCE         = "DG109";

    // EDGING_SPEC 미존재 (정확매칭 + '*' fallback 모두 실패) 는 사용자 사양에 따라
    // IllegalStateException 그대로 — DG 코드 미할당 (데이터 정합성 운영 이슈로 처리).
}
