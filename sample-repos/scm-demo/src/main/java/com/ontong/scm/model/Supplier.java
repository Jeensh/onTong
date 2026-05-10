package com.ontong.scm.model;

import java.util.List;

public class Supplier {
    private String supplierId;
    private String name;
    private String region;
    private double qualityScore;
    private int avgLeadTimeDays;
    private List<String> suppliedProducts;

    public Supplier(String supplierId, String name, String region) {
        this.supplierId = supplierId;
        this.name = name;
        this.region = region;
    }

    public String getSupplierId() { return supplierId; }
    public String getName() { return name; }
    public String getRegion() { return region; }
    public double getQualityScore() { return qualityScore; }
    public void setQualityScore(double score) { this.qualityScore = score; }
    public int getAvgLeadTimeDays() { return avgLeadTimeDays; }
    public void setAvgLeadTimeDays(int days) { this.avgLeadTimeDays = days; }
    public List<String> getSuppliedProducts() { return suppliedProducts; }
    public void setSuppliedProducts(List<String> products) { this.suppliedProducts = products; }
}
