package com.ontong.scm.procurement;

import com.ontong.scm.model.Supplier;

import java.time.LocalDate;

public class PurchaseOrderService {
    private final SupplierEvaluator supplierEvaluator;

    public PurchaseOrderService(SupplierEvaluator supplierEvaluator) {
        this.supplierEvaluator = supplierEvaluator;
    }

    public String createPurchaseOrder(String productId, int quantity, Supplier supplier) {
        String poId = "PO-" + System.currentTimeMillis();
        LocalDate expectedDelivery = LocalDate.now().plusDays(supplier.getAvgLeadTimeDays());
        return poId;
    }

    public String createAutoPurchaseOrder(String productId, int quantity) {
        Supplier best = supplierEvaluator.selectBestSupplier(productId);
        return createPurchaseOrder(productId, quantity, best);
    }

    public void confirmReceipt(String purchaseOrderId, int receivedQuantity) {
        // Mark PO as received and trigger goods receipt
    }

    public void handleShortage(String purchaseOrderId, int expectedQty, int actualQty) {
        int shortage = expectedQty - actualQty;
        if (shortage > 0) {
            // Create supplementary PO for the shortage
        }
    }
}
