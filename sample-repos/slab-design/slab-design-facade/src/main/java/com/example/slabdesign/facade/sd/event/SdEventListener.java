package com.example.slabdesign.facade.sd.event;

import org.springframework.stereotype.Component;

/**
 * sd task 의 Kafka 이벤트 수신 진입점.
 * P1 placeholder — class 골격만.
 * P3 (Edges) 에서 @KafkaListener 또는 Spring Cloud Stream Consumer 함수 추가 예정.
 *   - 설계 변경 이벤트 수신 → history 적재
 *   - 외부 트리거 이벤트 → working 작업 큐잉
 */
@Component
public class SdEventListener {
    // P3: @KafkaListener / Functional Bean (Consumer<>) 추가
}
