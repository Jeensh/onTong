# 온톨로지 시드 데이터 명세서

> **대상**: Claude Code
> **목적**: Layer 1·2의 모든 시드 데이터를 정의한다. 이 문서대로 JSON 파일을 만들어 `backend/modeling/ontology/data/`에 저장한다.
> **버전**: v1.0

---

# Section A. Layer 1 — Term & TermCategory

## A-1. terms.json

`backend/modeling/ontology/data/terms.json`:

```json
{
  "categories": [
    {"id": "cat_weight", "korean_name": "단중 계열", "description": "Slab/Coil의 무게 관련 용어"},
    {"id": "cat_dimension", "korean_name": "치수 계열", "description": "폭/길이/두께 관련 용어"},
    {"id": "cat_equipment", "korean_name": "설비 계열", "description": "연주/열연/냉연 설비 관련 용어"},
    {"id": "cat_concept", "korean_name": "개념 계열", "description": "압연/분할 등 추상 개념"},
    {"id": "cat_error", "korean_name": "에러 계열", "description": "설계 에러 코드"}
  ],
  "terms": [
    {
      "id": "term_unit_weight",
      "korean_name": "단중",
      "english_name": "UnitWeight",
      "aliases": ["중량", "톤"],
      "category": "weight",
      "description": "Slab 또는 코일 1개의 무게"
    },
    {
      "id": "term_order_weight",
      "korean_name": "주문단중",
      "english_name": "OrderWeight",
      "aliases": [],
      "category": "weight",
      "description": "고객 주문 기준 코일 1개 무게"
    },
    {
      "id": "term_slab_weight",
      "korean_name": "Slab단중",
      "english_name": "SlabWeight",
      "aliases": [],
      "category": "weight",
      "description": "Slab 1개의 무게 (분할 전 기준)"
    },
    {
      "id": "term_target_weight",
      "korean_name": "Target단중",
      "english_name": "TargetWeight",
      "aliases": ["목표단중"],
      "category": "weight",
      "description": "주문처리 시스템에서 입력되는 목표 단중"
    },
    {
      "id": "term_packaging_weight",
      "korean_name": "포장단중",
      "english_name": "PackagingWeight",
      "aliases": [],
      "category": "weight",
      "description": "포장 기준 단중 (보정 적용)"
    },
    {
      "id": "term_width",
      "korean_name": "폭",
      "english_name": "Width",
      "aliases": [],
      "category": "dimension",
      "description": "Slab 또는 Coil의 폭 (mm)"
    },
    {
      "id": "term_target_width",
      "korean_name": "목표폭",
      "english_name": "TargetWidth",
      "aliases": [],
      "category": "dimension",
      "description": "주문에서 요구하는 목표 폭"
    },
    {
      "id": "term_hr_target_width",
      "korean_name": "열연목표폭",
      "english_name": "HRTargetWidth",
      "aliases": [],
      "category": "dimension",
      "description": "열연 단계의 목표 폭"
    },
    {
      "id": "term_length",
      "korean_name": "길이",
      "english_name": "Length",
      "aliases": [],
      "category": "dimension",
      "description": "Slab/Coil 길이 (mm)"
    },
    {
      "id": "term_thickness",
      "korean_name": "두께",
      "english_name": "Thickness",
      "aliases": [],
      "category": "dimension",
      "description": "Slab의 두께 (연주설비 mold 두께와 동일)"
    },
    {
      "id": "term_continuous_caster",
      "korean_name": "연주설비",
      "english_name": "ContinuousCaster",
      "aliases": ["CC", "연주", "연속주조설비"],
      "category": "equipment",
      "description": "연속 주조 설비"
    },
    {
      "id": "term_hot_rolling_mill",
      "korean_name": "열연설비",
      "english_name": "HotRollingMill",
      "aliases": ["HSM", "HRM", "열연"],
      "category": "equipment",
      "description": "열간 압연 설비"
    },
    {
      "id": "term_cold_rolling_mill",
      "korean_name": "냉연설비",
      "english_name": "ColdRollingMill",
      "aliases": ["CSM", "냉연"],
      "category": "equipment",
      "description": "냉간 압연 설비"
    },
    {
      "id": "term_edging",
      "korean_name": "Edging",
      "english_name": "Edging",
      "aliases": ["에징"],
      "category": "concept",
      "description": "압연 시 양쪽 폭을 줄이는 작업"
    },
    {
      "id": "term_split_count",
      "korean_name": "분할수",
      "english_name": "SplitCount",
      "aliases": [],
      "category": "concept",
      "description": "Slab 1개를 코일 N개로 나누는 수"
    },
    {
      "id": "term_yield_rate",
      "korean_name": "실수율",
      "english_name": "YieldRate",
      "aliases": [],
      "category": "concept",
      "description": "주문량 대비 실제 생산 가능 비율"
    },
    {
      "id": "term_3pass",
      "korean_name": "3pass",
      "english_name": "ThreePass",
      "aliases": ["3패스"],
      "category": "concept",
      "description": "3회 압연 통과 설계 방식"
    },
    {
      "id": "term_design_policy",
      "korean_name": "Slab설계방침",
      "english_name": "SlabDesignPolicy",
      "aliases": [],
      "category": "concept",
      "description": "Slab단중최대화 vs 제품단중최대화 결정 정책"
    },
    {
      "id": "term_dg320",
      "korean_name": "DG320",
      "english_name": "DG320",
      "aliases": ["에징매칭불가"],
      "category": "error",
      "description": "Edging 기준에 매칭되는 주문이 없음"
    }
  ],
  "relations": [
    {"from": "term_order_weight", "to": "term_unit_weight", "type": "IS_A"},
    {"from": "term_slab_weight", "to": "term_unit_weight", "type": "IS_A"},
    {"from": "term_target_weight", "to": "term_unit_weight", "type": "IS_A"},
    {"from": "term_packaging_weight", "to": "term_unit_weight", "type": "IS_A"},
    {"from": "term_target_width", "to": "term_width", "type": "IS_A"},
    {"from": "term_hr_target_width", "to": "term_width", "type": "IS_A"},
    {"from": "term_edging", "to": "term_3pass", "type": "RELATED_TO"},
    {"from": "term_edging", "to": "term_hr_target_width", "type": "RELATED_TO"},
    {"from": "term_dg320", "to": "term_edging", "type": "RELATED_TO"}
  ]
}
```

**총량**: 5 카테고리, 19 Term, 9 관계

---

# Section B. Layer 2 — Step

## B-1. steps.json

`backend/modeling/ontology/data/steps.json`:

```json
{
  "steps": [
    {
      "id": "step_1",
      "step_number": 1,
      "korean_name": "두께 계산",
      "english_name": "Thickness Calculation",
      "description": "Slab두께 = 연주설비 mold 두께",
      "task_id": "SD030_01",
      "step_type": "calculation"
    },
    {
      "id": "step_2",
      "step_number": 2,
      "korean_name": "1차 폭범위 계산",
      "english_name": "Primary Width Range",
      "description": "max/min(목표폭+Edging능력, 연주/열연 폭범위)",
      "formula": "max(연주설비하한폭, 열연설비하한폭, 열연목표폭+열연Edging능력하한)",
      "task_id": "SD030_01",
      "step_type": "calculation"
    },
    {
      "id": "step_3",
      "step_number": 3,
      "korean_name": "1차 길이범위 계산",
      "english_name": "Primary Length Range",
      "description": "max/min(연주/열연 길이범위)",
      "task_id": "SD030_01",
      "step_type": "calculation"
    },
    {
      "id": "step_4",
      "step_number": 4,
      "korean_name": "1차 단중범위 계산",
      "english_name": "Primary Weight Range",
      "description": "두께 × 폭 × 길이 × 비중(7.82)",
      "task_id": "SD030_01",
      "step_type": "calculation"
    },
    {
      "id": "step_5",
      "step_number": 5,
      "korean_name": "2차 단중하한 계산",
      "english_name": "Secondary Weight Lower",
      "description": "max(여러 단중 제약 — 1차범위, 특정고객사, 냉연최소, 열연Min)",
      "task_id": "SD030_01",
      "step_type": "calculation"
    },
    {
      "id": "step_6",
      "step_number": 6,
      "korean_name": "2차 단중상한 계산",
      "english_name": "Secondary Weight Upper",
      "description": "min(여러 단중 제약 — 열연Max, 임가공, 전도제한, 외경제한, 냉연생산가능, Slab설계제약)",
      "task_id": "SD030_01",
      "step_type": "calculation"
    },
    {
      "id": "step_7",
      "step_number": 7,
      "korean_name": "분할수 계산",
      "english_name": "Split Count",
      "description": "최대분할수 = 소수점절상(2차단중상한 / 주문단중상한 / 보정상수 / 실수율)",
      "task_id": "SD030_01",
      "step_type": "calculation"
    },
    {
      "id": "step_8",
      "step_number": 8,
      "korean_name": "매수 및 목표단중 계산",
      "english_name": "Unit Count & Target Weight",
      "description": "분할수×매수 Loop, 단중만족율 기반 결정",
      "task_id": "SD030_01",
      "step_type": "loop"
    },
    {
      "id": "step_10",
      "step_number": 10,
      "korean_name": "2차 폭범위 계산",
      "english_name": "Secondary Width Range",
      "description": "단중 역산으로 폭범위 재계산",
      "formula": "Slab단중 / (1차길이 × 두께 × 비중)",
      "task_id": "SD030_01",
      "step_type": "calculation"
    },
    {
      "id": "step_12",
      "step_number": 12,
      "korean_name": "Target 폭 계산",
      "english_name": "Target Width",
      "description": "최종 Slab 목표폭 (10mm 단위 올림)",
      "task_id": "SD030_01",
      "step_type": "calculation"
    },
    {
      "id": "step_13",
      "step_number": 13,
      "korean_name": "Target 폭 재계산 (3pass)",
      "english_name": "Target Width Recalc 3pass",
      "description": "3pass Edging 능력 적용하여 재계산",
      "task_id": "SD030_01",
      "step_type": "branch"
    },
    {
      "id": "step_14",
      "step_number": 14,
      "korean_name": "Target 길이 계산",
      "english_name": "Target Length",
      "description": "Target단중/Target폭/두께",
      "task_id": "SD030_01",
      "step_type": "calculation"
    }
  ],
  "precedence": [
    [1, 2], [2, 3], [3, 4], [4, 5], [5, 6], [6, 7], [7, 8],
    [8, 10], [10, 12], [12, 13], [13, 14]
  ],
  "depends_on": [
    {"from": 10, "to": 8, "via_variable": "SlabWeight"},
    {"from": 12, "to": 8, "via_variable": "SlabWeight"}
  ]
}
```

**총량**: 12 Step, 11 PRECEDES 관계, 2 DEPENDS_ON 관계

---

# Section C. Layer 2 — Standard (SC 기준 16종)

## C-1. standards.json

`backend/modeling/ontology/data/standards.json`:

```json
{
  "standards": [
    {
      "id": "std_sc030",
      "code": "SC030",
      "korean_name": "연주설비사양기준",
      "english_name": "ContinuousCasterSpec",
      "category": "equipment_spec",
      "description": "연주설비별 두께/폭/길이 사양"
    },
    {
      "id": "std_sc040",
      "code": "SC040",
      "korean_name": "열연설비사양기준",
      "english_name": "HotRollingMillSpec",
      "category": "equipment_spec",
      "description": "열연설비별 폭/길이 사양"
    },
    {
      "id": "std_sc060",
      "code": "SC060",
      "korean_name": "코일외경제한기준",
      "english_name": "CoilOuterDiameter",
      "category": "weight_constraint",
      "description": "코일 외경 제약"
    },
    {
      "id": "std_sc070",
      "code": "SC070",
      "korean_name": "열연Edging능력기준",
      "english_name": "HRMEdgingCapability",
      "category": "equipment_capability",
      "description": "목표폭 구간별 Edging 능력 범위"
    },
    {
      "id": "std_sc071",
      "code": "SC071",
      "korean_name": "열연Edging규격그룹기준",
      "english_name": "HREdgingSpecGroup",
      "category": "equipment_capability",
      "description": "Edging 규격 그룹 분류"
    },
    {
      "id": "std_sc080",
      "code": "SC080",
      "korean_name": "열연압연Min단중기준",
      "english_name": "HRMinWeight",
      "category": "weight_constraint",
      "description": "열연 압연 가능 최소 단중"
    },
    {
      "id": "std_sc090",
      "code": "SC090",
      "korean_name": "열연압연Max단중기준",
      "english_name": "HRMaxWeight",
      "category": "weight_constraint",
      "description": "열연 압연 가능 최대 단중"
    },
    {
      "id": "std_sc100",
      "code": "SC100",
      "korean_name": "냉연최소단중하한기준",
      "english_name": "CSMMinWeight",
      "category": "weight_constraint",
      "description": "냉연 최소 단중 하한"
    },
    {
      "id": "std_sc110",
      "code": "SC110",
      "korean_name": "임가공생산가능단중상한기준",
      "english_name": "OEMMaxWeight",
      "category": "weight_constraint",
      "description": "임가공 생산가능 단중 상한"
    },
    {
      "id": "std_sc160",
      "code": "SC160",
      "korean_name": "단중만족상수",
      "english_name": "WeightSatisfactionConstant",
      "category": "design_policy",
      "description": "단중 최대화 vs 제품단중 최대화 결정 상수"
    },
    {
      "id": "std_sc170",
      "code": "SC170",
      "korean_name": "코일분할불가기준",
      "english_name": "CoilSplitProhibition",
      "category": "split_constraint",
      "description": "분할 불가 코일 조건"
    },
    {
      "id": "std_sc270",
      "code": "SC270",
      "korean_name": "전강Slab설계제약기준",
      "english_name": "EntireSlabDesignLimit",
      "category": "design_constraint",
      "description": "전강 Slab 설계 제약"
    },
    {
      "id": "std_sc290",
      "code": "SC290",
      "korean_name": "특정고객사설계제한기준",
      "english_name": "SpecificCustomerLimit",
      "category": "customer_constraint",
      "description": "특정 고객사별 단중 제약"
    },
    {
      "id": "std_sc370",
      "code": "SC370",
      "korean_name": "박판인도허용상한주문량보정기준",
      "english_name": "DeliveryAllowance",
      "category": "weight_constraint",
      "description": "박판 인도 허용 상한 주문량 보정"
    }
  ],
  "step_uses_standard": {
    "1": ["SC030"],
    "2": ["SC030", "SC040", "SC070", "SC071"],
    "3": ["SC030", "SC040"],
    "5": ["SC040", "SC080", "SC100", "SC290"],
    "6": ["SC040", "SC060", "SC090", "SC110", "SC170", "SC270", "SC290"],
    "7": ["SC370"],
    "8": ["SC160", "SC370"],
    "13": ["SC070"]
  }
}
```

**총량**: 14 Standard, 22 USES_STANDARD 관계

---

# Section D. Layer 1 ↔ Layer 2 Bridge

## D-1. bridges.json

`backend/modeling/ontology/data/bridges.json`:

```json
{
  "term_to_step": [
    {"term": "term_thickness", "step_number": 1, "role": "output"},
    {"term": "term_edging", "step_number": 2, "role": "internal"},
    {"term": "term_hr_target_width", "step_number": 2, "role": "input"},
    {"term": "term_dg320", "step_number": 2, "role": "error_trigger"},
    {"term": "term_slab_weight", "step_number": 5, "role": "output"},
    {"term": "term_slab_weight", "step_number": 6, "role": "output"},
    {"term": "term_split_count", "step_number": 7, "role": "output"},
    {"term": "term_yield_rate", "step_number": 7, "role": "input"},
    {"term": "term_split_count", "step_number": 8, "role": "internal"},
    {"term": "term_yield_rate", "step_number": 8, "role": "input"},
    {"term": "term_design_policy", "step_number": 8, "role": "internal"},
    {"term": "term_target_weight", "step_number": 8, "role": "output"},
    {"term": "term_target_width", "step_number": 12, "role": "output"},
    {"term": "term_edging", "step_number": 13, "role": "internal"},
    {"term": "term_3pass", "step_number": 13, "role": "internal"}
  ]
}
```

**총량**: 15 REFERS_TO_PROCESS 관계

---

# Section E. Layer 3 — Table & Form 매핑

## E-1. tables.json

`backend/modeling/ontology/data/tables.json`:

```json
{
  "tables": [
    {"id": "tb_sc030", "name": "TB_C40_050SC030", "schema": "POSPIA", "maps_to_standard": "SC030"},
    {"id": "tb_sc040", "name": "TB_C40_050SC040", "schema": "POSPIA", "maps_to_standard": "SC040"},
    {"id": "tb_sc060", "name": "TB_C40_050SC060", "schema": "POSPIA", "maps_to_standard": "SC060"},
    {"id": "tb_sc070", "name": "TB_C40_050SC070", "schema": "POSPIA", "maps_to_standard": "SC070"},
    {"id": "tb_sc071", "name": "TB_C40_050SC071", "schema": "POSPIA", "maps_to_standard": "SC071"},
    {"id": "tb_sc080", "name": "TB_C40_050SC080", "schema": "POSPIA", "maps_to_standard": "SC080"},
    {"id": "tb_sc090", "name": "TB_C40_050SC090", "schema": "POSPIA", "maps_to_standard": "SC090"},
    {"id": "tb_sc100", "name": "TB_C40_050SC100", "schema": "POSPIA", "maps_to_standard": "SC100"},
    {"id": "tb_sc110", "name": "TB_C40_050SC110", "schema": "POSPIA", "maps_to_standard": "SC110"},
    {"id": "tb_sc160", "name": "TB_C40_050SC160", "schema": "POSPIA", "maps_to_standard": "SC160"},
    {"id": "tb_sc170", "name": "TB_C40_050SC170", "schema": "POSPIA", "maps_to_standard": "SC170"},
    {"id": "tb_sc270", "name": "TB_C40_050SC270", "schema": "POSPIA", "maps_to_standard": "SC270"},
    {"id": "tb_sc290", "name": "TB_C40_050SC290", "schema": "POSPIA", "maps_to_standard": "SC290"},
    {"id": "tb_sc370", "name": "TB_C40_050SC370", "schema": "POSPIA", "maps_to_standard": "SC370"}
  ]
}
```

## E-2. Form 클래스 명명 패턴

jQAssistant로 추출한 :Class 중 다음 패턴을 자동으로 SC 기준에 매핑:

```python
FORM_TO_STANDARD = {
    "SDCastMachineSpecForm": "SC030",
    "SDHsmMachineSpecForm": "SC040",
    "SDCoilOutDiaRestricForm": "SC060",
    "SDHsmEdgingSpecForm": "SC070",
    "SDHsmWeightMinForm": "SC080",
    "SDStdRollMaxUnitForm": "SC090",
    "SDCsmMinWgtForm": "SC100",
    "SDOemWgtMaxRangeForm": "SC110",
    "SDWgtSatisfactionConstForm": "SC160",
    "SDHotCoilNotCuttableSpecForm": "SC170",
    "SDSlabDesignLimitationForm": "SC270",
    "SDSpecificCustomerWgtRestriForm": "SC290",
    "SDDeliveryAllowanceForm": "SC370",
}
```

---

# Section F. Layer 2 — Variable & ErrorCode

## F-1. variables.json

`backend/modeling/ontology/data/variables.json`:

```json
{
  "variables": [
    {"id": "var_thickness", "name": "Thickness", "korean_name": "두께", "type": "integer", "unit": "mm", "valid_range": "[200, 310]"},
    {"id": "var_target_width", "name": "TargetWidth", "korean_name": "목표폭", "type": "integer", "unit": "mm", "valid_range": "[750, 1650]"},
    {"id": "var_hr_target_width", "name": "HRTargetWidth", "korean_name": "열연목표폭", "type": "integer", "unit": "mm"},
    {"id": "var_primary_width_range", "name": "PrimaryWidthRange", "korean_name": "1차 폭범위", "type": "range", "unit": "mm"},
    {"id": "var_secondary_width_range", "name": "SecondaryWidthRange", "korean_name": "2차 폭범위", "type": "range", "unit": "mm"},
    {"id": "var_target_length", "name": "TargetLength", "korean_name": "목표길이", "type": "integer", "unit": "mm"},
    {"id": "var_slab_weight", "name": "SlabWeight", "korean_name": "Slab단중", "type": "integer", "unit": "kg"},
    {"id": "var_split_count", "name": "SplitCount", "korean_name": "분할수", "type": "integer", "unit": "ea"},
    {"id": "var_yield_rate", "name": "YieldRate", "korean_name": "실수율", "type": "float", "unit": "ratio", "valid_range": "[0.8, 1.0]"},
    {"id": "var_edging_capability", "name": "EdgingCapability", "korean_name": "Edging능력", "type": "range", "unit": "mm"}
  ],
  "step_inputs": {
    "1": ["var_thickness"],
    "2": ["var_hr_target_width", "var_edging_capability"],
    "4": ["var_thickness", "var_target_width", "var_target_length"],
    "7": ["var_slab_weight", "var_yield_rate"],
    "8": ["var_split_count", "var_yield_rate"],
    "10": ["var_slab_weight"],
    "12": ["var_slab_weight"]
  },
  "step_outputs": {
    "1": ["var_thickness"],
    "2": ["var_primary_width_range"],
    "5": ["var_slab_weight"],
    "6": ["var_slab_weight"],
    "7": ["var_split_count"],
    "10": ["var_secondary_width_range"],
    "12": ["var_target_width"]
  },
  "standard_constrains": [
    {"standard": "SC070", "variable": "var_primary_width_range"},
    {"standard": "SC080", "variable": "var_slab_weight"},
    {"standard": "SC090", "variable": "var_slab_weight"},
    {"standard": "SC290", "variable": "var_slab_weight"},
    {"standard": "SC100", "variable": "var_slab_weight"}
  ]
}
```

## F-2. error_codes.json

`backend/modeling/ontology/data/error_codes.json`:

```json
{
  "error_codes": [
    {
      "code": "DG320",
      "korean_message": "Edging 매칭 불가",
      "cause": "목표폭이 Edging 기준 범위 외",
      "severity": "error",
      "trigger_condition": "target_width NOT IN edging_table"
    }
  ],
  "step_triggers_error": [
    {"step_number": 2, "error_code": "DG320"}
  ]
}
```

---

# Section G. 데이터 검증 규칙

빌더 실행 후 다음을 자동 검증해야 한다:

```python
def verify_seed_data():
    """시드 데이터 무결성 검증"""
    
    # 1. terms.json
    assert len(terms_data["categories"]) == 5
    assert len(terms_data["terms"]) == 19
    
    # 2. steps.json
    assert len(steps_data["steps"]) == 12
    
    # 3. standards.json
    assert len(standards_data["standards"]) == 14
    
    # 4. bridges.json
    assert len(bridges_data["term_to_step"]) >= 14
    
    # 5. 모든 term의 category가 categories에 존재
    cat_ids = {c["id"] for c in terms_data["categories"]}
    for term in terms_data["terms"]:
        assert f"cat_{term['category']}" in cat_ids
    
    # 6. 모든 bridges의 term/step이 실제 존재
    term_ids = {t["id"] for t in terms_data["terms"]}
    step_nums = {s["step_number"] for s in steps_data["steps"]}
    for b in bridges_data["term_to_step"]:
        assert b["term"] in term_ids
        assert b["step_number"] in step_nums
```

이 검증을 통과해야 데이터 입력 완료로 간주한다.

---

# Section H. 데이터 통계 (목표)

빌드 완료 후 Neo4j에 다음만큼 데이터가 있어야 한다:

```
Layer 1 (Business):
  TermCategory: 5
  Term: 19
  IS_A: 6
  RELATED_TO: 3
  BELONGS_TO: 19

Layer 2 (Process):
  Step: 12
  Standard: 14
  Variable: 10
  ErrorCode: 1
  PRECEDES: 11
  DEPENDS_ON: 2
  USES_STANDARD: 22
  REQUIRES_INPUT: ~14
  PRODUCES_OUTPUT: ~7
  TRIGGERS_ON_FAIL: 1
  CONSTRAINS: 5

Bridge L1→L2:
  REFERS_TO_PROCESS: 15

Layer 3 (Code) — jQAssistant 추출 후:
  Class: ~10+
  Method: ~50+
  Table: 14
  
Bridge L2→L3:
  CALCULATES: ~12
  MAPS_TO_STANDARD: 14
  IMPLEMENTS: ~5

총: ~100 노드, ~170 관계 (Layer 3 포함 전)
총: ~200 노드, ~280 관계 (Layer 3 포함 후)
```
