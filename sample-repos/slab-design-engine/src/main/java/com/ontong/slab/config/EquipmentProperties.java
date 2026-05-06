package com.ontong.slab.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 설비 제약 파라미터. application.yml 의 `slab.equipment` 섹션에서 주입된다.
 *
 * 변경 시 운영 기준서와 동기화 필요. 특히 maxThicknessMm 는 강종별 압연
 * 능력 한계와 직결되므로 현장 엔지니어 승인 필수.
 */
@ConfigurationProperties(prefix = "slab.equipment")
public class EquipmentProperties {

    /** 압연기 최대 폭 (mm). 이 값보다 큰 Slab 는 압연 불가. */
    private double rollingMillMaxWidthMm = 2400.0;

    /** 가열로 최대 길이 (mm). 이 값보다 긴 Slab 는 가열로 진입 불가. */
    private double furnaceMaxLengthMm = 12000.0;

    /** 크레인 최대 하중 (kg). Slab 중량이 이 값을 넘으면 취급 불가. */
    private double craneMaxLoadKg = 45000.0;

    /** 최소 허용 두께 (mm). */
    private double minThicknessMm = 180.0;

    /**
     * 최대 허용 두께 (mm). 현재 설비 한계 기준.
     * NOTE: 운영 기준서와 불일치 가능 구간 — 현장 압연 한계치 문의 필요.
     */
    private double maxThicknessMm = 240.0;

    public double getRollingMillMaxWidthMm() {
        return rollingMillMaxWidthMm;
    }

    public void setRollingMillMaxWidthMm(double rollingMillMaxWidthMm) {
        this.rollingMillMaxWidthMm = rollingMillMaxWidthMm;
    }

    public double getFurnaceMaxLengthMm() {
        return furnaceMaxLengthMm;
    }

    public void setFurnaceMaxLengthMm(double furnaceMaxLengthMm) {
        this.furnaceMaxLengthMm = furnaceMaxLengthMm;
    }

    public double getCraneMaxLoadKg() {
        return craneMaxLoadKg;
    }

    public void setCraneMaxLoadKg(double craneMaxLoadKg) {
        this.craneMaxLoadKg = craneMaxLoadKg;
    }

    public double getMinThicknessMm() {
        return minThicknessMm;
    }

    public void setMinThicknessMm(double minThicknessMm) {
        this.minThicknessMm = minThicknessMm;
    }

    public double getMaxThicknessMm() {
        return maxThicknessMm;
    }

    public void setMaxThicknessMm(double maxThicknessMm) {
        this.maxThicknessMm = maxThicknessMm;
    }
}
