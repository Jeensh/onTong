package com.ontong.scm.order;

import com.ontong.scm.inventory.InventoryManager;
import com.ontong.scm.production.ProductionPlanner;
import com.ontong.scm.model.Product;

import java.time.LocalDate;
import java.util.List;

public class OrderService {
    private final InventoryManager inventoryManager;
    private final ProductionPlanner productionPlanner;

    public OrderService(InventoryManager inventoryManager, ProductionPlanner productionPlanner) {
        this.inventoryManager = inventoryManager;
        this.productionPlanner = productionPlanner;
    }

    public String createSalesOrder(String customerId, List<Product> items, LocalDate requestedDate) {
        String orderId = generateOrderId();
        for (Product item : items) {
            int available = inventoryManager.checkStock(item.getProductId());
            if (available < 1) {
                productionPlanner.requestProduction(item.getProductId(), 1, requestedDate);
            }
        }
        return orderId;
    }

    public OrderStatus getOrderStatus(String orderId) {
        return OrderStatus.RECEIVED;
    }

    public LocalDate estimateDeliveryDate(String orderId) {
        return LocalDate.now().plusDays(7);
    }

    public void cancelOrder(String orderId) {
        inventoryManager.releaseReservation(orderId);
    }

    private String generateOrderId() {
        return "SO-" + System.currentTimeMillis();
    }
}
