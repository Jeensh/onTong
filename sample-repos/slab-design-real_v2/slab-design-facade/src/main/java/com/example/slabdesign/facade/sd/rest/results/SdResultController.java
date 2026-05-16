package com.example.slabdesign.facade.sd.rest.results;

import com.example.slabdesign.store.sd.working.jpo.SlabResultJpo;
import com.example.slabdesign.store.sd.working.repository.SlabResultRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

/**
 * Slab 결과 (SLAB_RESULT) 조회 REST 컨트롤러.
 */
@RestController
@RequestMapping("/api/sd/results")
@Tag(name = "Results", description = "Slab result query")
public class SdResultController {

    private final SlabResultRepository repo;

    public SdResultController(SlabResultRepository repo) {
        this.repo = repo;
    }

    @Operation(summary = "주문번호 기준 슬랩 결과 목록 (1 주문 → N 슬랩)")
    @GetMapping
    public List<SlabResultJpo> byOrder(
            @RequestParam String cmpCd,
            @RequestParam String orgCd,
            @RequestParam String orderNo) {
        return repo.findByCmpCdAndOrgCdAndOrderNo(cmpCd, orgCd, orderNo);
    }

    @Operation(summary = "슬랩 번호 단건 조회")
    @GetMapping("/{slabNo}")
    public SlabResultJpo bySlabNo(@PathVariable String slabNo) {
        return repo.findFirstBySlabNo(slabNo)
            .orElseThrow(() -> new ResponseStatusException(
                HttpStatus.NOT_FOUND, "SLAB_RESULT not found: " + slabNo));
    }
}
