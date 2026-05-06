package com.ontong.slab.domain;

/**
 * 강종 정의. 밀도 단위는 kg/m^3.
 *
 * 중량 산출 공식은 밀도 × 체적으로 통일한다.
 * 신규 강종 추가 시 밀도를 반드시 정의하고, 강종별 최소 두께는
 * 별도 기준서 표를 참조한다.
 */
public enum SteelGrade {

    /** 일반 구조용 압연강재. 밀도 7850 kg/m^3. */
    SS400(7850.0),

    /** 용접 구조용 압연강재. 밀도 7860 kg/m^3. */
    SM490(7860.0),

    /** 조선용 고장력강. 밀도 7850 kg/m^3. */
    AH36(7850.0);

    private final double densityKgPerM3;

    SteelGrade(double densityKgPerM3) {
        this.densityKgPerM3 = densityKgPerM3;
    }

    public double getDensityKgPerM3() {
        return densityKgPerM3;
    }
}
