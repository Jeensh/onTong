package com.example.slabdesign.facade.sd.rest.working;

import com.example.slabdesign.facade.sd.rest.working.dto.SingleDesignRequest;
import com.example.slabdesign.facade.sd.rest.working.dto.SingleDesignResponse;
import com.example.slabdesign.feature.sd.driver.SdDriver;
import com.example.slabdesign.feature.sd.process.working.wrapper.AlgorithmException;
import com.example.slabdesign.feature.sd.trace.TraceCollector;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/sd/working")
@Tag(name = "Working", description = "21-step slab design execution")
public class SdWorkingController {

    private final SdDriver driver;

    public SdWorkingController(SdDriver driver) {
        this.driver = driver;
    }

    @Operation(summary = "온톨로지·소 단위 배치 Slab 설계 (v1 호환)")
    @PostMapping("/batch")
    public SdDriver.BatchResult batchDesign(
            @RequestParam String cmpCd,
            @RequestParam String orgCd) {
        return driver.batchDesign(cmpCd, orgCd);
    }

    @Operation(summary = "주문 1건 Slab 설계 (옵션: trace=true 로 step-별 입출력 trace 반환)")
    @PostMapping("/single")
    public SingleDesignResponse singleDesign(
            @RequestBody SingleDesignRequest req,
            @RequestParam(defaultValue = "false") boolean trace) {
        TraceCollector collector = trace ? new TraceCollector() : null;
        try {
            SDSlabEntity slab = driver.singleDesign(req.cmpCd(), req.orgCd(), req.orderNo(), collector);
            List<SDSlabEntity> slabs = slab == null ? List.of() : List.of(slab);
            return collector == null
                ? SingleDesignResponse.ok(slabs)
                : SingleDesignResponse.okWithTrace(slabs, collector.traces());
        } catch (AlgorithmException e) {
            return SingleDesignResponse.fail(
                e.getErrorCode(),
                e.getMessage(),
                collector == null ? null : collector.traces());
        }
    }
}
