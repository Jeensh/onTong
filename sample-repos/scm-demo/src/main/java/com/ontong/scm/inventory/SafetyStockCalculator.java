package com.ontong.scm.inventory;

import com.ontong.scm.model.Product;

public class SafetyStockCalculator {
    private static final double SERVICE_LEVEL_Z = 1.65; // 95% service level

    public int calculate(String productId) {
        double avgDemand = getAverageDailyDemand(productId);
        double demandStdDev = getDemandStandardDeviation(productId);
        int leadTime = getLeadTimeDays(productId);
        return (int) Math.ceil(SERVICE_LEVEL_Z * demandStdDev * Math.sqrt(leadTime));
    }

    public int calculateWithSeasonality(String productId, int month) {
        int base = calculate(productId);
        double factor = getSeasonalFactor(month);
        return (int) Math.ceil(base * factor);
    }

    private double getAverageDailyDemand(String productId) {
        return 100.0;
    }

    private double getDemandStandardDeviation(String productId) {
        return 20.0;
    }

    private int getLeadTimeDays(String productId) {
        return 7;
    }

    private double getSeasonalFactor(int month) {
        if (month >= 10 || month <= 1) return 1.5; // peak season
        return 1.0;
    }
}
