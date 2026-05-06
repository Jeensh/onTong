package com.ontong.slab.constraint;

/**
 * 제약 위반 사유. 위반한 제약의 이름과 원인 값을 함께 전달한다.
 */
public record ConstraintViolation(String rule, String detail) {
}
