# Slab 설계 시스템 + 온톨로지 — 작업 안내

> Claude Code에게 작업을 요청할 때 **이 README부터 읽고** 어떤 순서로 진행할지 결정하세요.

---

## 📦 이 폴더에 있는 두 문서

| 파일 | 역할 |
|------|------|
| **slab-design-domain-knowledge.md** | 업무처리기준서의 모든 도메인 지식 정리 (이미지에서 발췌한 내용) |
| **slab-design-system-spec.md** | Spring Boot 시스템 개발 명세 (위 도메인을 코드로 구현) |

---

## 🎯 두 문서의 관계

```
[도메인 지식 문서]                    [시스템 개발 문서]
slab-design-domain-               slab-design-system-
knowledge.md                       spec.md
        ↓                                  ↓
   (개념·기준·계산식)              (Class·Method·Table)
        ↓                                  ↓
   온톨로지 Layer 1·2          온톨로지 Layer 3 (자동 추출)
   (수동 입력)                  (jQAssistant)
        ↓                                  ↓
        └────────── Bridge 관계 ──────────┘
                  (Method ↔ Step,
                   Form ↔ Standard)
```

---

## 🏗 작업 순서

```
Step 1. Spring Boot 시스템 구축 (1~2주)
   → slab-design-system-spec.md 따라 구현
   → 결과: sample-repos/scm-demo/ 에 동작하는 시스템

Step 2. 시스템에 jQAssistant 적용 (1일)
   → mvn jqassistant:scan 실행
   → 결과: Neo4j에 Class/Method/Table 자동 등록

Step 3. 온톨로지 Layer 1·2 수동 입력 (3~5일)
   → slab-design-domain-knowledge.md 기반
   → 결과: Neo4j에 Term/Step/Standard 등록

Step 4. Layer 간 Bridge 연결 (1~2일)
   → 메서드명 패턴 매칭 + LLM 보조
   → 결과: 3-Layer 통합 그래프 완성
```

---

## 🎬 Claude Code 호출 예시

### 케이스 1: 시스템부터 만들기
```
docs/slab-design-system-spec.md 따라서
sample-repos/scm-demo/ 위치에 Spring Boot 시스템을 만들어줘.

다음 사항을 지켜줘:
- 명명 규칙(calculatePrimaryWidthRange 등)을 절대 어기지 말 것
- 도메인 지식이 필요하면 slab-design-domain-knowledge.md 참고
- 검증 시나리오(예제 주문 01S3047892010)가 통과하도록 구현
```

### 케이스 2: 온톨로지부터 만들기 (시스템은 미완)
```
docs/slab-design-domain-knowledge.md 기반으로 
온톨로지 Layer 1·2를 구축해줘.
시스템(Layer 3)은 jQAssistant로 나중에 자동 추출 예정.
```

### 케이스 3: 통합 진행
```
docs/README-slab-system.md 부터 읽고,
1) 먼저 sample-repos/scm-demo에 Spring Boot 시스템 구현
2) 그 다음 온톨로지 Layer 1·2 수동 입력
3) jQAssistant로 Layer 3 자동 추출
4) 검증 쿼리 통과 확인

순서로 진행해줘.
```

---

## 🔑 핵심 명명 규칙 (절대 어기지 말 것)

자동 매핑이 동작하려면 다음 규칙을 반드시 지켜야 합니다.

### 메서드명 → Step 자동 매핑
```
calculateThickness*              → Step 1
calculatePrimaryWidth*           → Step 2
calculatePrimaryLength*          → Step 3
calculatePrimaryWeight*          → Step 4
calculateSecondaryWeightLower*   → Step 5
calculateSecondaryWeightUpper*   → Step 6
calculateMaxSplitCount / calculateSplitCount → Step 7
calculateUnitCount*              → Step 8
checkTargetWeight*               → Step 9
calculateSecondaryWidth*         → Step 10
calculateSecondaryLength*        → Step 11
calculateTargetWidth (정확히 일치) → Step 12
calculateTargetWidthFor3Pass     → Step 13
calculateTargetLength            → Step 14
```

### Form 클래스명 → SC 기준 자동 매핑
```
SDCastMachineSpecForm        → SC030
SDHsmMachineSpecForm         → SC040
SDCoilOutDiaRestricForm      → SC060
SDHsmEdgingSpecForm          → SC070
SDHrEdgingSpecGroupForm      → SC071
SDHsmWeightMinForm           → SC080
SDStdRollMaxUnitForm         → SC090
SDCsmMinWgtForm              → SC100
SDOemWgtMaxRangeForm         → SC110
SDWgtSatisfactionConstForm   → SC160
SDHotCoilNotCuttableSpecForm → SC170
SDSlabDesignLimitationForm   → SC270
SDSpecificCustomerWgtRestriForm → SC290
SDDeliveryAllowanceForm      → SC370
```

### 테이블명
```
TB_C40_050SC030 ~ TB_C40_050SC370
```

---

## ✅ 완성 기준

### Spring Boot 시스템
- [ ] `mvn test` 모든 테스트 통과
- [ ] 예제 주문 01S3047892010 → 정상 결과 (Step 1-14 모두 동작)
- [ ] DG320 시나리오 → 에러 정상 발생
- [ ] Swagger UI에서 API 문서 확인

### 온톨로지
- [ ] `mvn jqassistant:scan` → Neo4j에 Class/Method 자동 등록
- [ ] Layer 1 (Term 19개) 등록
- [ ] Layer 2 (Step 12개 + Standard 14개) 등록
- [ ] Bridge 검증: `MATCH (m:Method)-[:CALCULATES]->(s:Step) RETURN count(*)`
       → 12개 이상 (Step 1-14 매핑)
- [ ] Bridge 검증: `MATCH (c:Class)-[:RELATES_TO_STANDARD]->(std)`
       → 14개 (모든 SC 기준 매핑)

---

## 🎬 데모 시나리오

```
1. Spring Boot 시스템 실행
   curl -X POST http://localhost:8080/api/slab-design/execute/01S3047892010
   
   → 응답: 14단계 모두 수행된 설계 결과 + Step 로그

2. Neo4j Browser에서 온톨로지 확인
   http://localhost:7474
   
   쿼리: 
   MATCH (t:Term {korean_name:'Edging'})
         -[:REFERS_TO_PROCESS]->(s:Step)
         <-[:CALCULATES]-(m:Method)
         <-[:CONTAINS]-(c:Class)
   RETURN c.name, m.name, s.korean_name
   
   → 결과: 'Edging' 한 단어로부터 SlabDesignService.calculatePrimaryWidthRange()까지 추적
```

---

## 📌 자주 묻는 질문

### Q1. 시스템과 온톨로지를 동시에 진행해도 되나?
A. 네. 시스템은 `sample-repos/scm-demo/`, 온톨로지는 `backend/modeling/ontology/`로 분리되어 있어 병렬 가능합니다.

### Q2. 시스템 만든 후 온톨로지 Layer 1·2 수동 입력해야 하나?
A. 네. Layer 3는 jQAssistant로 자동, Layer 1·2는 도메인 지식이라 사람이 입력합니다.

### Q3. 명명 규칙 어기면 어떻게 되나?
A. jQAssistant가 자동 매핑을 못 하므로 Bridge 관계가 안 생깁니다. **온톨로지 가치의 80%가 사라집니다.**

### Q4. 데이터베이스는 H2로 시작해도 되나?
A. 네. 개발은 H2, 운영은 PostgreSQL. application-dev.yml과 application-prod.yml로 분리.

### Q5. 강종(API-X52 등)별로 비중이 달라야 하지 않나?
A. 도메인 문서 Rule 4 참고. **일단 7.82로 통일**하고, 추후 강종별 차이는 별도 작업으로.

---

## 🚀 빨리 시작하기

```bash
# 1. 레포 클론
git clone https://github.com/Jeensh/onTong.git
cd onTong

# 2. 작업 브랜치
git checkout -b feat/slab-system-and-ontology

# 3. Claude Code 호출
# 위의 "Claude Code 호출 예시" 케이스 3 사용
```
