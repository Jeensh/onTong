package com.ontong.scm.production;

import java.time.LocalDate;

public class WorkOrderProcessor {
    public String createWorkOrder(String productId, int quantity, LocalDate dueDate) {
        String workOrderId = "WO-" + System.currentTimeMillis();
        allocateMaterials(workOrderId, productId, quantity);
        assignWorkstation(workOrderId);
        return workOrderId;
    }

    public void startProduction(String workOrderId) {
        // Begin manufacturing process
    }

    public void reportCompletion(String workOrderId, int producedQuantity, int defectCount) {
        double yieldRate = (double)(producedQuantity - defectCount) / producedQuantity;
        if (yieldRate < 0.95) {
            flagQualityIssue(workOrderId, yieldRate);
        }
    }

    public void reschedule(String workOrderId, LocalDate newDueDate) {
        // Update work order schedule
    }

    private void allocateMaterials(String workOrderId, String productId, int quantity) {
        // Reserve raw materials from BOM
    }

    private void assignWorkstation(String workOrderId) {
        // Assign to available production line
    }

    private void flagQualityIssue(String workOrderId, double yieldRate) {
        // Notify quality engineer
    }
}
