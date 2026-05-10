package com.ontong.bridge;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;

import java.util.Collections;
import java.util.List;
import java.util.Map;

/**
 * slab-design 의 Oracle-bound Repository / Kafka Producer 를 mock 으로 swap.
 *
 * ⚠️ 실 사용 시 user 가 Slab-디자인 의 정확한 인터페이스 (예: SdOrderRepository,
 *    CastSpecRepository, SdSlabRepository, KafkaProducerService 등) 를 import 후
 *    아래 @Bean 주석 해제 + 본인 클래스 시그니처에 맞게 수정 필요.
 *
 * 현재는 컴파일 가능한 빈 skeleton — slab-design 의 인터페이스 노출 후 채울 것.
 *
 * 패턴:
 *
 *     @Primary
 *     @Bean
 *     public SdOrderRepository mockSdOrderRepo() {
 *         return new SdOrderRepository() {
 *             @Override public List<SDOrderEntity> findDesignable(String cmpCd, String orgCd) {
 *                 return Collections.emptyList(); // HeadlessRunner 가 stdin 으로 직접 주입하므로 빈 list
 *             }
 *             // 다른 메서드들은 throw new UnsupportedOperationException()
 *         };
 *     }
 *
 * Spring 은 같은 인터페이스에 대해 @Primary 가 붙은 Bean 을 우선 주입 → 원본 Repository 자리에 mock 들어감.
 */
@Configuration
public class MockConfig {

    /**
     * 빈 placeholder — 사용자가 slab-design 인터페이스 확인 후 채울 것.
     *
     * 핵심 mock 대상 후보 (slab-design 코드 인용 기준):
     *  - SdOrderExtractor               (slab-design-feature)
     *  - CastSpecRepository / HrSpecRepository / EdgingSpecRepository ... (slab-design-store)
     *  - SdSlabRepository / SdHistoryRepository                          (적재 — no-op)
     *  - KafkaProducer / EventPublisher                                  (no-op)
     */
    @Bean
    public Object mockMarker() {
        return new Object();
    }
}
