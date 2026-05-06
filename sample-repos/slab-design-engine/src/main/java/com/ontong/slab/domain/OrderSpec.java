package com.ontong.slab.domain;

/**
 * 수주 사양. 납기·강종·요구 치수 범위를 포함한다.
 *
 * 엔진은 이 범위 안에서 설비 제약을 만족하는 최대 중량의 Slab 를 찾는다.
 * 최소값 0 이하 또는 최대 < 최소 는 유효하지 않은 입력으로 본다.
 */
public class OrderSpec {

    private final String orderId;
    private final SteelGrade grade;
    private final double minLengthMm;
    private final double maxLengthMm;
    private final double minWidthMm;
    private final double maxWidthMm;
    private final double minThicknessMm;
    private final double maxThicknessMm;

    public OrderSpec(
            String orderId,
            SteelGrade grade,
            double minLengthMm,
            double maxLengthMm,
            double minWidthMm,
            double maxWidthMm,
            double minThicknessMm,
            double maxThicknessMm) {
        this.orderId = orderId;
        this.grade = grade;
        this.minLengthMm = minLengthMm;
        this.maxLengthMm = maxLengthMm;
        this.minWidthMm = minWidthMm;
        this.maxWidthMm = maxWidthMm;
        this.minThicknessMm = minThicknessMm;
        this.maxThicknessMm = maxThicknessMm;
    }

    public String getOrderId() {
        return orderId;
    }

    public SteelGrade getGrade() {
        return grade;
    }

    public double getMinLengthMm() {
        return minLengthMm;
    }

    public double getMaxLengthMm() {
        return maxLengthMm;
    }

    public double getMinWidthMm() {
        return minWidthMm;
    }

    public double getMaxWidthMm() {
        return maxWidthMm;
    }

    public double getMinThicknessMm() {
        return minThicknessMm;
    }

    public double getMaxThicknessMm() {
        return maxThicknessMm;
    }
}
