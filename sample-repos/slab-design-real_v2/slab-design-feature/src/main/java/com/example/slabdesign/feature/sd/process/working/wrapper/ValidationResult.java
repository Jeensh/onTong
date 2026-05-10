package com.example.slabdesign.feature.sd.process.working.wrapper;

/**
 * sd · 정합성 점검 결과 DTO.
 * pass / fail + 에러코드 + 메시지 carrier.
 */
public class ValidationResult {

    private final boolean passed;
    private final String errorCode;
    private final String message;

    private ValidationResult(boolean passed, String errorCode, String message) {
        this.passed = passed;
        this.errorCode = errorCode;
        this.message = message;
    }

    public static ValidationResult pass() {
        return new ValidationResult(true, null, null);
    }

    public static ValidationResult fail(String errorCode, String message) {
        return new ValidationResult(false, errorCode, message);
    }

    public boolean isPassed() { return passed; }
    public boolean isFailed() { return !passed; }
    public String getErrorCode() { return errorCode; }
    public String getMessage() { return message; }
}
