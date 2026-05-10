package com.example.slabdesign.feature.sd.driver;

import com.example.slabdesign.feature.sd.designer.SdDesigner;
import com.example.slabdesign.feature.sd.process.working.action.SdOrderExtractor;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

/**
 * sd · driver · 복합 job 흐름 제어.
 *
 * 여러 designer 호출의 배치 그룹핑·순서 제어.
 * 공유 상태(가용 설비 풀, 배치 컨텍스트) 관리 후보 (P3 시나리오 확장 가능).
 *
 * 배치 흐름:
 *   1. SdOrderExtractor 로 설계 가능 후보 주문 추출 (진도 C/D, 종결 ≠ 1·2)
 *   2. 각 후보에 대해 SdDesigner.design() 호출 → SDSlabEntity 생성
 *   3. 결과 집계 (총/처리완료/skip + 처리된 Slab 리스트)
 *
 * NOTE: @Transactional 미적용 — 배치 전체가 단일 tx 면 한 Slab fail 이 모두 rollback.
 *       각 designer.design() 내부의 history 적재는 자체 @Transactional 로 처리됨.
 *
 * @author 김XX (2017-07-04 최초작성)
 * @author 박XX (2018-10-22 batch 단위 tx 분리)
 * @author 이XX (2021-02-03 BatchResult record 도입, skip 카운트 분리)
 *
 * 운영이슈 P-2018-0312 (2018-09-30):
 *   - 단일 tx 환경에서 1건 fail → 전체 rollback 으로 야간 배치 0건 처리
 *   - 해결: designer.design() 내부 @Transactional 분리 — 박XX 패치
 *
 * TODO(2022-11-05 이XX): 후보 주문 다건 시 병렬 처리 (현재 순차) — OPS-2540
 */
@Component
public class SdDriver {

    private final SdOrderExtractor extractor;
    private final SdDesigner designer;

    @Autowired
    public SdDriver(SdOrderExtractor extractor, SdDesigner designer) {
        this.extractor = extractor;
        this.designer = designer;
    }

    /**
     * 회사·소 단위 배치 Slab 설계.
     */
    public BatchResult batchDesign(String cmpCd, String orgCd) {
        List<SDOrderEntity> candidates = extractor.extractDesignableOrders(cmpCd, orgCd);
        List<SDSlabEntity> processed = new ArrayList<>();
        int skipped = 0;

        for (SDOrderEntity order : candidates) {
            SDSlabEntity slab = designer.design(order);
            if (slab != null) {
                processed.add(slab);
            } else {
                skipped++;
            }
        }
        return new BatchResult(candidates.size(), processed.size(), skipped, processed);
    }

    /**
     * 배치 결과 — 총 후보 수 / 처리 완료 / skip / 처리된 Slab 리스트.
     */
    public record BatchResult(
        int total,
        int processedCount,
        int skippedCount,
        List<SDSlabEntity> processedSlabs
    ) {}
}
