package com.ontong.bridge;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.springframework.boot.CommandLineRunner;
import org.springframework.context.annotation.Lazy;
import org.springframework.stereotype.Component;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * stdin JSON → SdDesigner.design() → stdout JSON.
 *
 * 주의:
 *  - SdDesigner / SDOrderEntity / SDSlabEntity 의 정확한 패키지 경로는 slab-design 의 실제
 *    클래스 정의에 따라 import 가 달라질 수 있음. 컴파일 에러로 빠르게 확인 후 수정.
 *  - 현재 코드는 slab-design 이 mvn install 되어있고 SdDesigner 가 @Component 로 등록되어
 *    있다는 가정. 만약 생성자 인자로 collaborators 를 받는다면 MockConfig 에서 @Primary
 *    Bean 으로 mock 주입 필요.
 *
 * 입력 JSON 예 (Python 측 runner.py 가 보냄):
 *   {
 *     "order": {
 *       "cmpCd": "K", "orgCd": "K01", "orderNo": "ORD-001",
 *       "stockCode": 0, "orderWidth": "1200", ...
 *     },
 *     "fixtures": {  // 선택, mock Repository 가 사용
 *       "castSpec": [...]
 *     }
 *   }
 *
 * 출력 JSON:
 *   {
 *     "ok": true,
 *     "slab": { ...SDSlabEntity 필드... },
 *     "designStatus": "OK" | "FAIL",
 *     "errorCode": null | "DG..."
 *   }
 *
 * 에러 시:
 *   { "ok": false, "error": "...", "stack": "..." }
 */
@Component
public class HeadlessRunner implements CommandLineRunner {

    // SdDesigner 를 lazy 로 받음 — 실제 호출 시점에 주입 (Spring context 완전 기동 후)
    // ⚠️ slab-design 의 SdDesigner 정확한 fully-qualified name 으로 교체 필요:
    //    예: com.example.slabdesign.feature.sd.designer.SdDesigner
    @Lazy
    private final Object sdDesigner;

    private final ObjectMapper objectMapper;

    public HeadlessRunner(@Lazy Object sdDesigner) {
        // 위 sdDesigner Object 는 placeholder — 실 사용 시 SdDesigner 타입으로 교체.
        this.sdDesigner = sdDesigner;

        this.objectMapper = new ObjectMapper();
        this.objectMapper.registerModule(new JavaTimeModule());
        this.objectMapper.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
    }

    @Override
    public void run(String... args) throws Exception {
        String stdin = readAllStdin();
        Map<String, Object> response = new LinkedHashMap<>();

        try {
            JsonNode root = objectMapper.readTree(stdin);
            JsonNode order = root.path("order");

            // ⚠️ TODO (사용자) — SdDesigner 호출 부분.
            //    1) JsonNode order → SDOrderEntity 변환
            //       (objectMapper.treeToValue(order, SDOrderEntity.class) 가능, getter/setter 있다면)
            //    2) sdDesigner.design(orderEntity) 호출
            //    3) 반환된 SDSlabEntity → Map<String, Object> 직렬화
            //
            // 현재는 stub: 입력 그대로 echo + ok=true.
            response.put("ok", true);
            response.put("slab", Map.of(
                "_stub", true,
                "echoed_order_no", order.path("orderNo").asText("")
            ));
            response.put("designStatus", "OK");
            response.put("errorCode", null);
            response.put("note", "Java Bridge stub — SdDesigner 호출부는 사용자 구현 필요 (HeadlessRunner.java TODO 참조)");

        } catch (Exception e) {
            response.put("ok", false);
            response.put("error", e.getClass().getSimpleName() + ": " + e.getMessage());
            response.put("stack", stackTrace(e));
        }

        // stdout 은 오직 JSON — 다른 모든 로그는 stderr 로 가야 함 (BridgeApp 에서 banner off).
        System.out.println(objectMapper.writeValueAsString(response));
        System.out.flush();
    }

    private String readAllStdin() throws Exception {
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(System.in, StandardCharsets.UTF_8))) {
            return reader.lines().collect(Collectors.joining("\n"));
        }
    }

    private String stackTrace(Throwable t) {
        java.io.StringWriter sw = new java.io.StringWriter();
        t.printStackTrace(new java.io.PrintWriter(sw));
        return sw.toString();
    }
}
