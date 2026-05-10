package com.example.slabdesign.facade.sd.rest.working;

import com.example.slabdesign.feature.sd.driver.SdDriver;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * sd · working · Slab 설계 작업 실행 API.
 *
 * 엔드포인트:
 *   POST /api/sd/working/batch?cmpCd=...&orgCd=...
 *     → 회사·소 단위 배치 설계 실행 (SdDriver.batchDesign).
 *     → 결과: { total, processedCount, skippedCount, processedSlabs[] }
 */
@RestController
@RequestMapping("/api/sd/working")
@CrossOrigin(origins = "*")    // onTong 프론트(:3000)에서 직접 호출 허용
public class SdWorkingController {

    private final SdDriver driver;

    @Autowired
    public SdWorkingController(SdDriver driver) {
        this.driver = driver;
    }

    /** 회사·소 단위 배치 Slab 설계. */
    @PostMapping("/batch")
    public SdDriver.BatchResult batchDesign(
            @RequestParam String cmpCd,
            @RequestParam String orgCd) {
        return driver.batchDesign(cmpCd, orgCd);
    }
}
