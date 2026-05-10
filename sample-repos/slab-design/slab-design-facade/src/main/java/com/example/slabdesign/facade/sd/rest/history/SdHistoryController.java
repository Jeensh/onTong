package com.example.slabdesign.facade.sd.rest.history;

import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * sd · history: 설계 과정 이력 저장·조회 API.
 * P1 placeholder.
 * P2 에서 설계 시도 / 수정 / 승인 이력 CRUD + 검색 엔드포인트 추가.
 */
@RestController
@RequestMapping("/api/sd/history")
public class SdHistoryController {
    // P2: GET /history/{designId}, GET /history?orderId=..., POST /history (수동 적재)
}
