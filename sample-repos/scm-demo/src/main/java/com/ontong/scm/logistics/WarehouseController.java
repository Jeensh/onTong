package com.ontong.scm.logistics;

import com.ontong.scm.model.Warehouse;

import java.util.List;

public class WarehouseController {
    private final List<Warehouse> warehouses;

    public WarehouseController(List<Warehouse> warehouses) {
        this.warehouses = warehouses;
    }

    public Warehouse selectWarehouse(String productId, int quantity) {
        return warehouses.stream()
                .filter(w -> w.getAvailableSpace() >= quantity)
                .findFirst()
                .orElseThrow(() -> new IllegalStateException("No warehouse capacity available"));
    }

    public void processInbound(String warehouseId, String productId, int quantity) {
        // Receive goods, update stock, assign storage location
    }

    public void processOutbound(String warehouseId, String orderId, String productId, int quantity) {
        // Pick, pack, stage for shipping
    }

    public void cycleCount(String warehouseId) {
        // Periodic inventory count and reconciliation
    }
}
