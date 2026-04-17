package com.ontong.scm.model;

import java.math.BigDecimal;
import java.util.List;

public class Product {
    private String productId;
    private String name;
    private String category;
    private BigDecimal unitPrice;
    private List<String> bomComponents;
    private int safetyStockLevel;
    private int leadTimeDays;

    public Product(String productId, String name, String category) {
        this.productId = productId;
        this.name = name;
        this.category = category;
    }

    public String getProductId() { return productId; }
    public String getName() { return name; }
    public String getCategory() { return category; }
    public BigDecimal getUnitPrice() { return unitPrice; }
    public void setUnitPrice(BigDecimal unitPrice) { this.unitPrice = unitPrice; }
    public List<String> getBomComponents() { return bomComponents; }
    public void setBomComponents(List<String> bom) { this.bomComponents = bom; }
    public int getSafetyStockLevel() { return safetyStockLevel; }
    public void setSafetyStockLevel(int level) { this.safetyStockLevel = level; }
    public int getLeadTimeDays() { return leadTimeDays; }
    public void setLeadTimeDays(int days) { this.leadTimeDays = days; }
}
