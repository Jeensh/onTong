package com.example.slabdesign.facade.sd.rest.history;

import com.example.slabdesign.store.sd.history.jpo.SlabDesignHistJpo;
import com.example.slabdesign.store.sd.history.repository.SlabDesignHistRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 21-step Slab 설계 이력 (SLAB_DESIGN_HIST) 조회 REST 컨트롤러.
 *
 * - byOrder: 주문 단위 이력 (실패 포함, EventTime 오름차순)
 * - bySlab : 성공 Slab 단위 이력 (StepNo 오름차순)
 */
@RestController
@RequestMapping("/api/sd/history")
@Tag(name = "History", description = "21-step design history (post-execution)")
public class SdHistoryController {

    private final SlabDesignHistRepository repo;

    public SdHistoryController(SlabDesignHistRepository repo) {
        this.repo = repo;
    }

    @Operation(summary = "주문 기준 step 별 이력 (실패 포함, eventTime asc)")
    @GetMapping
    public List<SlabDesignHistJpo> byOrder(
            @RequestParam String cmpCd,
            @RequestParam String orgCd,
            @RequestParam String orderNo) {
        return repo.findByCmpCdAndOrgCdAndOrderNoOrderByEventTimeAsc(cmpCd, orgCd, orderNo);
    }

    @Operation(summary = "Slab 기준 step 별 이력 (성공 케이스, stepNo asc)")
    @GetMapping("/slab/{slabNo}")
    public List<SlabDesignHistJpo> bySlab(
            @RequestParam String cmpCd,
            @RequestParam String orgCd,
            @PathVariable String slabNo) {
        return repo.findByCmpCdAndOrgCdAndSlabNoOrderByStepNoAsc(cmpCd, orgCd, slabNo);
    }
}
