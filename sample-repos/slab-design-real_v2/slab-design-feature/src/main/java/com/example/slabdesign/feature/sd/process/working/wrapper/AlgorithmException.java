package com.example.slabdesign.feature.sd.process.working.wrapper;

/**
 * sd · 알고리즘 단계 실패 시 throw.
 * SdDesigner 가 catch 하여 SdHistoryAction.recordAlgorithmFailure 로 history 적재.
 *
 * EDGING_SPEC 미존재처럼 데이터 정합성 운영 이슈는 이 클래스 대신 IllegalStateException 사용 (사용자 사양).
 */
public class AlgorithmException extends RuntimeException {

    private static final long serialVersionUID = 1L;

    private final int stepNo;
    private final String stepName;
    private final String errorCode;

    public AlgorithmException(int stepNo, String stepName, String errorCode, String message) {
        super(message);
        this.stepNo = stepNo;
        this.stepName = stepName;
        this.errorCode = errorCode;
    }

    public int getStepNo() { return stepNo; }
    public String getStepName() { return stepName; }
    public String getErrorCode() { return errorCode; }
}
