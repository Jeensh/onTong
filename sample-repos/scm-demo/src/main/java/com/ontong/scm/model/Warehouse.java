package com.ontong.scm.model;

import java.util.Map;

public class Warehouse {
    private String warehouseId;
    private String location;
    private int capacity;
    private Map<String, Integer> stockLevels;

    public Warehouse(String warehouseId, String location, int capacity) {
        this.warehouseId = warehouseId;
        this.location = location;
        this.capacity = capacity;
    }

    public String getWarehouseId() { return warehouseId; }
    public String getLocation() { return location; }
    public int getCapacity() { return capacity; }
    public Map<String, Integer> getStockLevels() { return stockLevels; }
    public void setStockLevels(Map<String, Integer> levels) { this.stockLevels = levels; }

    public int getAvailableSpace() {
        if (stockLevels == null) return capacity;
        int used = stockLevels.values().stream().mapToInt(Integer::intValue).sum();
        return capacity - used;
    }
}
