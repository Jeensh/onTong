# Java Bridge — slab-design 무수정 호출

`slab-design` 자바 시스템을 **수정 없이** 호출하기 위한 별도 Spring Boot CLI.
Oracle/Kafka 의존성은 `@Primary @Bean` override 로 mock 으로 swap.

## 빌드 절차 (사용자 1회 수행)

```bash
# 1) slab-design 의 jar 들을 local m2 에 install
cd /Users/jiyoon/claude/onTong/sample-repos/slab-design
./mvnw install -DskipTests

# 2) Java Bridge 빌드 (fat jar)
cd /Users/jiyoon/claude/onTong/backend/simulation/jvm_bridge/java_bridge
mvn package -DskipTests

# 3) 빌드 산출물 확인
ls -la target/java-bridge-1.0.0.jar
```

빌드 성공 시 Python `is_bridge_available()` 가 True 반환.

## 환경변수 (선택)

```bash
# JAR 경로 명시 (target/ 외 위치에 두려면)
export SIMULATION_JAVA_BRIDGE_JAR=/path/to/java-bridge-1.0.0.jar
```

## 수동 호출 테스트

```bash
echo '{"order": {"cmpCd": "K", "orgCd": "K01", "orderNo": "ORD-001", "stockCode": 0}}' \
  | java -jar target/java-bridge-1.0.0.jar
```

기대 응답: `{"ok": true, "slab": {...}, "designStatus": "OK", "errorCode": null, ...}` (현재는 stub).

## ⚠️ 사용자가 완성해야 하는 부분

현재 `HeadlessRunner.java` 는 **stub** — SdDesigner 호출 부분이 비어있음.
사용자가 slab-design 의 정확한 클래스 시그니처 확인 후 다음 4 개를 완성:

1. **`HeadlessRunner.java` import**
   ```java
   import com.example.slabdesign.feature.sd.designer.SdDesigner;
   import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
   import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
   ```

2. **`HeadlessRunner` 생성자 시그니처 변경**
   ```java
   private final SdDesigner sdDesigner;
   public HeadlessRunner(SdDesigner sdDesigner) { this.sdDesigner = sdDesigner; }
   ```

3. **`run()` 의 TODO 영역에 실제 호출**
   ```java
   SDOrderEntity orderEntity = objectMapper.treeToValue(order, SDOrderEntity.class);
   SDSlabEntity slab = sdDesigner.design(orderEntity);
   response.put("slab", objectMapper.convertValue(slab, Map.class));
   response.put("designStatus", slab.getDesignStatus());  // FIELD NAME 확인
   response.put("errorCode", slab.getErrorCode());
   ```

4. **`MockConfig.java` 에 slab-design 의 Repository 인터페이스별 mock @Bean 추가**
   ```java
   @Primary
   @Bean
   public SdOrderExtractor mockSdOrderExtractor() {
       return new SdOrderExtractor(...) {
           @Override
           public List<SDOrderEntity> extractDesignableOrders(String cmpCd, String orgCd) {
               return Collections.emptyList();  // 또는 stdin 의 orders 반환
           }
       };
   }
   ```

   각 Repository 인터페이스마다 동일 패턴. 메서드는 `Collections.emptyList()` /
   `null` / `throw new UnsupportedOperationException()` 등으로 채움.

## 트러블슈팅

| 증상 | 원인 / 대응 |
|---|---|
| `Could not find artifact com.example.slabdesign:slab-design-feature` | 1단계 `mvnw install` 미수행. 먼저 slab-design 빌드 |
| `Failed to load class SdDesigner` | scanBasePackages 누락. `BridgeApp.java` 의 패키지 경로 확인 |
| `Bean of type X not found` | 해당 Repository 가 mock 으로 swap 안 됨. `MockConfig.java` 에 @Primary @Bean 추가 |
| stdout 에 로그 섞임 | `application.yml` 의 logging.level 이 WARN 인지 확인 + Banner off |
| `Cannot deserialize SDOrderEntity` | Jackson 이 entity 의 setter/생성자 부재 → `@JsonCreator` 우회 또는 수동 변환 |

## 디자인 의도

- **slab-design 폴더 무수정**: pom.xml 의 dependency 로만 참조. 그쪽 코드는 read-only.
- **Spring 자체의 Bean override**: 자바 코드 수정 없이 Repository 만 mock 으로 교체 가능.
- **stdin/stdout JSON**: Python subprocess 와 명료한 인터페이스. 로그는 stderr.
- **fat jar**: 외부 classpath 설정 필요 없음. `java -jar ...` 로 즉시 실행.
- **재실행 친화**: JVM cold start 200~500ms. 1000건 differential test 시 ~5분.
  필요하면 동일 JVM 안에 long-running server 모드 추가 가능 (향후 후보).
