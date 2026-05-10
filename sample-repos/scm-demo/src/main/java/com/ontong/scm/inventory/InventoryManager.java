package com.ontong.scm.inventory;

import com.ontong.scm.model.Warehouse;
import com.ontong.scm.procurement.PurchaseOrderService;

import java.util.Map;

public class InventoryManager {
    private final Warehouse mainWarehouse;
    private final PurchaseOrderService purchaseOrderService;
    private final SafetyStockCalculator safetyStockCalculator;

    public InventoryManager(Warehouse mainWarehouse, PurchaseOrderService purchaseOrderService,
                            SafetyStockCalculator safetyStockCalculator) {
        this.mainWarehouse = mainWarehouse;
        this.purchaseOrderService = purchaseOrderService;
        this.safetyStockCalculator = safetyStockCalculator;
    }

    public int checkStock(String productId) {
        Map<String, Integer> levels = mainWarehouse.getStockLevels();
        return levels != null ? levels.getOrDefault(productId, 0) : 0;
    }

    public void reserveStock(String productId, int quantity, String orderId) {
        int available = checkStock(productId);
        if (available < quantity) {
            throw new IllegalStateException("Insufficient stock for " + productId);
        }
    }

    public void releaseReservation(String orderId) {
        // Release reserved stock back to available pool
    }

    public void receiveGoods(String productId, int quantity, String purchaseOrderId) {
        // Add received goods to warehouse stock
    }

    public void checkReorderPoint(String productId) {
        int current = checkStock(productId);
        int safetyLevel = safetyStockCalculator.calculate(productId);
        if (current <= safetyLevel) {
            purchaseOrderService.createAutoPurchaseOrder(productId, safetyLevel * 2);
        }
    }
}
