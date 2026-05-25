package com.example.slabdesign.feature.sd.driver;

import com.example.slabdesign.feature.sd.designer.SdDesigner;
import com.example.slabdesign.feature.sd.process.working.action.SdOrderExtractor;
import com.example.slabdesign.feature.sd.trace.TraceCollector;
import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

/**
 * sd · driver · 복합 job 흐름 제어.
 *
 * 두 진입점:
 *   - {@link #batchDesign(String, String)} — 온톨로지·소 단위 배치 설계 (extractor 로 후보 수집).
 *   - {@link #singleDesign(String, String, String)} — 단일 주문 설계 (golden scenario / API 단건 호출용).
 *
 * 배치 흐름:
 *   1. SdOrderExtractor 로 설계 가능 후보 주문 추출 (진도 C/D, 종결 ≠ 1·2)
 *   2. 각 후보에 대해 SdDesigner.design() 호출 → SDSlabEntity 생성
 *   3. 결과 집계 (총/처리완료/skip + 처리된 Slab 리스트)
 *
 * NOTE: @Transactional 미적용 — 배치 전체가 단일 tx 면 한 Slab fail 이 모두 rollback.
 *       각 designer.design() 내부의 history 적재는 자체 @Transactional 로 처리됨.
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
     * 온톨로지·소 단위 배치 Slab 설계.
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
     * 단일 주문 Slab 설계 (trace 미사용).
     *
     * @return 설계 성공 시 SDSlabEntity, 실패 시 null. 주문 미존재 시 IllegalArgumentException.
     */
    public SDSlabEntity singleDesign(String cmpCd, String orgCd, String orderNo) {
        return singleDesign(cmpCd, orgCd, orderNo, null);
    }

    /**
     * 단일 주문 Slab 설계 + 옵션 trace.
     * 진도/종결 필터 미적용 — golden scenario / facade API 단건 호출 용도.
     */
    public SDSlabEntity singleDesign(String cmpCd, String orgCd, String orderNo, TraceCollector trace) {
        SDOrderEntity order = extractor.findOne(cmpCd, orgCd, orderNo);
        if (order == null) {
            throw new IllegalArgumentException(
                "order not found: cmpCd=" + cmpCd + ", orgCd=" + orgCd + ", orderNo=" + orderNo);
        }
        return designer.design(order, trace);
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
