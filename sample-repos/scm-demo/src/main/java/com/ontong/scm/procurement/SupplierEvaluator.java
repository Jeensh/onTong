package com.ontong.scm.procurement;

import com.ontong.scm.model.Supplier;

import java.util.Comparator;
import java.util.List;

public class SupplierEvaluator {
    private static final double QUALITY_WEIGHT = 0.4;
    private static final double LEAD_TIME_WEIGHT = 0.3;
    private static final double COST_WEIGHT = 0.3;

    public Supplier selectBestSupplier(String productId) {
        List<Supplier> candidates = getCandidateSuppliers(productId);
        return candidates.stream()
                .max(Comparator.comparingDouble(this::calculateScore))
                .orElseThrow(() -> new IllegalStateException("No supplier for " + productId));
    }

    public double calculateScore(Supplier supplier) {
        double qualityScore = supplier.getQualityScore() * QUALITY_WEIGHT;
        double leadTimeScore = (1.0 / supplier.getAvgLeadTimeDays()) * 100 * LEAD_TIME_WEIGHT;
        return qualityScore + leadTimeScore;
    }

    public List<Supplier> rankSuppliers(String productId) {
        return getCandidateSuppliers(productId).stream()
                .sorted(Comparator.comparingDouble(this::calculateScore).reversed())
                .toList();
    }

    private List<Supplier> getCandidateSuppliers(String productId) {
        return List.of();
    }
}
