package com.ontong.slab.domain;

/**
 * 직육면체 Slab 치수 + 강종. 길이/폭/두께 단위는 mm.
 *
 * 중량 = 강종 밀도 × (L × W × T) 로 계산한다. 모든 치수는 양수여야 하며
 * 생성자에서 음수나 0을 받으면 IllegalArgumentException 을 던진다.
 */
public class Slab {

    private final double lengthMm;
    private final double widthMm;
    private final double thicknessMm;
    private final SteelGrade grade;

    public Slab(double lengthMm, double widthMm, double thicknessMm, SteelGrade grade) {
        if (lengthMm <= 0 || widthMm <= 0 || thicknessMm <= 0) {
            throw new IllegalArgumentException("slab dimensions must be positive: " + lengthMm + "x" + widthMm + "x" + thicknessMm);
        }
        if (grade == null) {
            throw new IllegalArgumentException("grade is required");
        }
        this.lengthMm = lengthMm;
        this.widthMm = widthMm;
        this.thicknessMm = thicknessMm;
        this.grade = grade;
    }

    public double getLengthMm() {
        return lengthMm;
    }

    public double getWidthMm() {
        return widthMm;
    }

    public double getThicknessMm() {
        return thicknessMm;
    }

    public SteelGrade getGrade() {
        return grade;
    }

    /**
     * 체적을 m^3 단위로 반환한다. mm^3 → m^3 환산계수는 1e-9.
     */
    public double volumeM3() {
        return (lengthMm * widthMm * thicknessMm) * 1e-9;
    }

    /**
     * 중량 = 밀도 × 체적 (kg).
     */
    public double weightKg() {
        return grade.getDensityKgPerM3() * volumeM3();
    }
}
