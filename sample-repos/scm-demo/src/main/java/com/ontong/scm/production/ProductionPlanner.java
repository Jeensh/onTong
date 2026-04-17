package com.ontong.scm.production;

import com.ontong.scm.inventory.InventoryManager;
import com.ontong.scm.model.Product;

import java.time.LocalDate;
import java.util.List;

public class ProductionPlanner {
    private final WorkOrderProcessor workOrderProcessor;

    public ProductionPlanner(WorkOrderProcessor workOrderProcessor) {
        this.workOrderProcessor = workOrderProcessor;
    }

    public String requestProduction(String productId, int quantity, LocalDate dueDate) {
        int capacityAvailable = checkCapacity(dueDate);
        if (capacityAvailable < quantity) {
            return scheduleOverflow(productId, quantity, dueDate);
        }
        return workOrderProcessor.createWorkOrder(productId, quantity, dueDate);
    }

    public List<String> generateWeeklyPlan(LocalDate weekStart) {
        // Generate production schedule for the week based on demand forecast
        return List.of();
    }

    public void adjustPlan(String workOrderId, LocalDate newDueDate) {
        workOrderProcessor.reschedule(workOrderId, newDueDate);
    }

    private int checkCapacity(LocalDate date) {
        return 500; // daily production capacity
    }

    private String scheduleOverflow(String productId, int quantity, LocalDate dueDate) {
        LocalDate adjusted = dueDate.plusDays(3);
        return workOrderProcessor.createWorkOrder(productId, quantity, adjusted);
    }
}
