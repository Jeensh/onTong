package com.example.slabdesign.facade.exception;

import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * 전역 예외 처리.
 * P1 placeholder — 구체적 @ExceptionHandler 매핑은 P2/P3 에서 도메인 예외 정의 후 추가.
 */
@RestControllerAdvice
public class GlobalExceptionHandler {
    // P2/P3: @ExceptionHandler(SdDomainException.class), @ExceptionHandler(ValidationException.class) ...
}
