package com.example.slabdesign.facade.sd.rest.seed;

import com.example.slabdesign.facade.sd.rest.seed.dto.ScenarioMeta;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/sd/seed")
@Tag(name = "Seed", description = "Reset DB and inspect golden scenario metadata")
public class SdSeedController {

    private final SeedService seed;

    private static final List<ScenarioMeta> SCENARIOS = List.of(
        new ScenarioMeta("S1", "ORD20260510001", "일반 COIL 주문 (golden path)", "K   K   ", "1 slab"),
        new ScenarioMeta("S2", "ORD20260510002", "다중 분할 (maxSplitCount=4)", "KK      ", "4 slabs"),
        new ScenarioMeta("S3", "ORD20260510003", "A-a loop fallback", "KKKK    ", "splitCount-1 후 성공"),
        new ScenarioMeta("S4", "ORD20260510004", "DG004 포장단중 cross-check fail", "KK      ", "design fail + hist row"),
        new ScenarioMeta("S5", "ORD20260510005", "최소 활성 공정 (SM, CRF)", "K      K", "1 slab, 누적실수율 = SM*CRF")
    );

    public SdSeedController(SeedService seed) {
        this.seed = seed;
    }

    @PostMapping("/reset")
    public Map<String, Object> reset() throws Exception {
        seed.reset();
        return Map.of("ok", true, "scenarios", SCENARIOS.stream().map(ScenarioMeta::id).toList());
    }

    @GetMapping("/scenarios")
    public List<ScenarioMeta> scenarios() {
        return SCENARIOS;
    }
}
