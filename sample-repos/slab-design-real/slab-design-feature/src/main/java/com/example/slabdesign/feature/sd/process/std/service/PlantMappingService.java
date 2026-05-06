package com.example.slabdesign.feature.sd.process.std.service;

import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;

/**
 * sd · std · 제강코드 → (연주코드, 머신코드) 매핑 서비스.
 *
 * 레거시 시스템에 하드코딩되어 있던 매핑을 그대로 이식.
 * CAST_SPEC 룩업 시 SDOrder.confirmedPlantCd[0] (제강 위치) 만 알 수 있으므로,
 * 이 서비스가 (CAST_CD, MACHINE_CD) 를 보충해서 6-컬럼 PK 룩업을 완성시킨다.
 *
 * 시나리오 확장 후보 (P3):
 *   - 매핑을 std DB 테이블 (PROC_MAPPING) 로 이전
 *   - 시나리오: "매핑 행 추가/변경 시 어떤 주문의 설계 결과가 영향?"
 */
@Service
public class PlantMappingService {

    /** (연주코드, 머신코드) 튜플. */
    public record PlantMapping(String castCd, String machineCd) {}

    private static final Map<String, PlantMapping> SM_TO_CAST_MACHINE = createMapping();

    private static Map<String, PlantMapping> createMapping() {
        // 레거시 하드코딩 — 실제 운영 매핑값은 스크럽
        Map<String, PlantMapping> m = new HashMap<>();
        m.put("A", new PlantMapping("CC1", "M1"));
        m.put("B", new PlantMapping("CC2", "M2"));
        m.put("C", new PlantMapping("CC3", "M3"));
        m.put("D", new PlantMapping("CC4", "M4"));
        return m;
    }

    /** smCd 에 대응하는 매핑 반환. 미등록 시 null. */
    public PlantMapping getMapping(String smCd) {
        if (smCd == null) return null;
        return SM_TO_CAST_MACHINE.get(smCd);
    }

    public boolean hasMapping(String smCd) {
        return smCd != null && SM_TO_CAST_MACHINE.containsKey(smCd);
    }
}
