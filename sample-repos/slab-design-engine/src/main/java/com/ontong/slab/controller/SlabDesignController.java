package com.ontong.slab.controller;

import com.ontong.slab.domain.OrderSpec;
import com.ontong.slab.domain.SteelGrade;
import com.ontong.slab.optimizer.DesignCandidate;
import com.ontong.slab.service.SlabDesignService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Slab 설계 REST API.
 *
 * POST /slabs/design — 수주 사양을 받아 최대 중량 Slab 반환.
 */
@RestController
@RequestMapping("/slabs")
public class SlabDesignController {

    private final SlabDesignService service;

    @Autowired
    public SlabDesignController(SlabDesignService service) {
        this.service = service;
    }

    @PostMapping("/design")
    public ResponseEntity<DesignResponse> design(@RequestBody DesignRequest req) {
        OrderSpec order = req.toOrderSpec();
        DesignCandidate best = service.design(order);
        return ResponseEntity.ok(DesignResponse.from(best));
    }

    public record DesignRequest(
            String orderId,
            SteelGrade grade,
            double minLengthMm,
            double maxLengthMm,
            double minWidthMm,
            double maxWidthMm,
            double minThicknessMm,
            double maxThicknessMm) {
        public OrderSpec toOrderSpec() {
            return new OrderSpec(orderId, grade, minLengthMm, maxLengthMm, minWidthMm, maxWidthMm, minThicknessMm, maxThicknessMm);
        }
    }

    public record DesignResponse(
            double lengthMm,
            double widthMm,
            double thicknessMm,
            SteelGrade grade,
            double weightKg) {
        public static DesignResponse from(DesignCandidate c) {
            return new DesignResponse(
                    c.slab().getLengthMm(),
                    c.slab().getWidthMm(),
                    c.slab().getThicknessMm(),
                    c.slab().getGrade(),
                    c.slab().weightKg());
        }
    }
}
