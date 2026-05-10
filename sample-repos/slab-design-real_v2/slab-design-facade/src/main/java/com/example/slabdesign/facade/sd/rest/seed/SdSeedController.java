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
        new ScenarioMeta("S1", "ORD20260510001", "일반 COIL 주문 (golden path: split fallback → 1 slab)",
            "K1 K    ", "1 slab"),
        new ScenarioMeta("S2", "ORD20260510002", "다중 슬랩 + A-a inner loop (split=2 + step10→step13)",
            "K1      ", "3 slabs"),
        new ScenarioMeta("S3", "ORD20260510003", "A-a inner-loop fallback (split=1 + step10→step13)",
            "K1KK    ", "2 slabs"),
        new ScenarioMeta("S4", "ORD20260510004", "DG004 validator cross-check fail",
            "K1      ", "design fail (validator) + hist row"),
        new ScenarioMeta("S5", "ORD20260510005", "최소 활성 공정 (SM, HR, CRF — HR 필수)",
            "K1     K", "1 slab")
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
