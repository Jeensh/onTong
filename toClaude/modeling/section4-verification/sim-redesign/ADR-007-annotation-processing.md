# ADR-007: Annotation Processing (Compile-time Meta) Handling

작성일: 2026-05-13
상태: 확정 (사용자 D 선택 응답)
선행: ADR-001 (Python twin), ADR-002 (Two-Engine + plugin)
관련: ADR-006 (annotation-based dispatch — Case 3)

## 컨텍스트

Java annotation 의 효과는 두 종류:

1. **Runtime reflection-based** — annotation 이 runtime 에 reflection 으로 인식되어 동작 변경
   - Spring `@Autowired`, `@Component`
   - JPA `@Entity`, `@Column`
   - Jackson `@JsonProperty`
   - JUnit `@Test`
   - **이건 ADR-002 의 plugins/<sys>/stubs/ 가 처리**

2. **Compile-time annotation processing** — annotation 이 javac 의 annotation processor 단계에서 인식되어 **추가 코드 생성**
   - Lombok `@Getter`/`@Setter`/`@Builder`/`@Data` (가장 흔함)
   - MapStruct `@Mapper`
   - Querydsl `@QueryEntity` (Q-class 생성)
   - Dagger `@Inject` (DI graph 생성)
   - 사용자 정의 annotation processor

(2) 가 이 ADR 의 대상. compile 시 생성된 code 가 source 에 보이지 않으나 bytecode 에 존재.

## 결정

Compile-time annotation 효과를 **Section 2 의 ontology 추출 단계에서 흡수**:

- Section 2 가 알려진 annotation processor 의 효과를 정적으로 시뮬레이션
- Synthesized method/class 가 ontology 에 정상 row 로 기록
- 합성기는 generated method 와 직접 작성 method 를 구별 안 함 — uniformly Python 화

알려진 processor 별 시뮬레이터:
- core: Lombok (`@Getter`/`@Setter`/`@Builder`/`@Data`/`@AllArgsConstructor`/`@NoArgsConstructor`/`@RequiredArgsConstructor`)
- plugins/<sys>/processors/: 사용자 정의 (MapStruct, custom)

## Section 2 의 작업

기존 AST extractor 에 annotation-aware pass 추가:

```python
# backend/modeling/code_layer/annotation_processor.py (신규)

LOMBOK_PROCESSORS = {
    "@Getter": process_getter,
    "@Setter": process_setter,
    "@Builder": process_builder,
    "@Data": process_data,  # @Getter + @Setter + @ToString + @EqualsAndHashCode
    "@AllArgsConstructor": process_all_args_ctor,
}

def process_getter(class_ast, field, ontology):
    # Lombok @Getter on `private String name` 생성: `public String getName() { return this.name; }`
    method_fqn = f"{class_ast.fqn}.get{capitalize(field.name)}"
    ontology.add_method(
        fqn=method_fqn,
        return_type=field.type,
        params=[],
        is_synthetic=True,           # annotation processor 생성 표시
        synthesized_from="@Getter",
        body_source="lombok_generated",
    )

def process_builder(class_ast, ontology):
    builder_fqn = f"{class_ast.fqn}.Builder"
    ontology.add_class(
        fqn=builder_fqn,
        is_synthetic=True,
        synthesized_from="@Builder",
        kind="builder",
    )
    # builder 의 fluent method 도 추가
    for field in class_ast.fields:
        ontology.add_method(
            fqn=f"{builder_fqn}.{field.name}",
            return_type=builder_fqn,
            params=[(field.name, field.type)],
            is_synthetic=True,
        )
    ontology.add_method(
        fqn=f"{builder_fqn}.build",
        return_type=class_ast.fqn,
        params=[],
        is_synthetic=True,
    )
```

`code_methods.is_synthetic` 컬럼 추가 (additive). 합성기 는 이 flag 무시 — 정상 method 처럼 처리.

## 각 annotation 별 Python 변환 패턴

### Lombok @Getter / @Setter

```java
@Getter @Setter
private BigDecimal slabThickness;
```

→ ontology 에 두 method (getSlabThickness / setSlabThickness) 자동 추가 → Python:

```python
class SDSlabEntity:
    def __init__(self):
        self._slab_thickness: BigDecimal | None = None

    @property
    def slab_thickness(self) -> BigDecimal | None:
        return self._slab_thickness

    @slab_thickness.setter
    def slab_thickness(self, value: BigDecimal):
        self._slab_thickness = value
```

또는 더 단순 (dataclass 가 사용되면):

```python
@dataclass
class SDSlabEntity:
    slab_thickness: BigDecimal | None = None
```

선택은 plugins/<sys>/contracts/style.toml 의 정책.

### Lombok @Builder

```java
@Builder
public class Order {
    String cmpCd;
    String orgCd;
    String productCd;
}
// 사용: Order o = Order.builder().cmpCd("K").orgCd("1").build();
```

→ ontology 가 OrderBuilder class + fluent methods 추가 → Python:

```python
@dataclass
class Order:
    cmp_cd: str | None = None
    org_cd: str | None = None
    product_cd: str | None = None

    @staticmethod
    def builder() -> "OrderBuilder":
        return OrderBuilder()

class OrderBuilder:
    def __init__(self):
        self._order = Order()
    def cmp_cd(self, v: str) -> "OrderBuilder":
        self._order.cmp_cd = v
        return self
    def org_cd(self, v: str) -> "OrderBuilder":
        self._order.org_cd = v
        return self
    def product_cd(self, v: str) -> "OrderBuilder":
        self._order.product_cd = v
        return self
    def build(self) -> Order:
        return self._order
```

### Lombok @Data

`@Data = @Getter + @Setter + @ToString + @EqualsAndHashCode + @RequiredArgsConstructor`. 각 sub-annotation 의 processor 가 chain 실행.

### MapStruct @Mapper (plugin 영역)

MapStruct 는 compile 시 mapper implementation 생성. 더 복잡 — plugin 작성:

```python
# plugins/<sys>/processors/mapstruct.py
def process_mapper(class_ast, ontology):
    # @Mapping(target="...", source="...") 추출
    # impl class 와 method body 생성 시뮬레이션
    ...
```

기본 mapping (`@Mapping(source="srcField", target="dstField")`) 만 핸들. 복잡 case (expression, qualifier, conditional) 는 SIGNATURE_LOCKED + plugin 확장 권장.

### Spring Boot @ConfigurationProperties

```java
@ConfigurationProperties(prefix = "app.config")
public class AppConfig {
    private String host;
    private int port;
}
```

→ ontology 가 binding 정보 기록 → Python:

```python
@dataclass
class AppConfig:
    host: str = ""
    port: int = 0

    @classmethod
    def from_config(cls, props: dict) -> "AppConfig":
        return cls(
            host=props["app.config.host"],
            port=int(props["app.config.port"]),
        )
```

## v2 Reality

verified: v2 는 Lombok 미사용 (직접 getter/setter 정의). Spring Boot annotation 만 사용 — `@Component`, `@Autowired`, `@Transactional`, `@Entity`. 모두 ADR-002 의 framework stub 영역.

→ 본 ADR 의 즉시 v2 작업 없음. **일반화 대상 system 이 Lombok 등을 사용하면 본 ADR 의 mechanism 활성**.

## Honest Limits

- **Annotation processor 의 generated code 가 복잡**: MapStruct, Querydsl 의 일부 기능은 정적 시뮬레이션 비용 큼. 일부 SIGNATURE_LOCKED 불가피
- **Annotation 의 동적 처리**: `@Autowired` 가 `@Qualifier` 존재 여부에 따라 동작 → ontology 가 모든 annotation 의 cross-reference 추적해야
- **Multi-stage processor**: A 가 코드 생성 → 그 코드에 B 적용 (e.g., Lombok 후 Spring Boot) → chain processing 순서 정의 필요
- **Custom annotation 의 비공개 processor**: 회사 내부 annotation processor 가 비공개 라이브러리에 있는 경우 — plugin 작성 불가능, SIGNATURE_LOCKED

## 결과

- Lombok 사용 system 의 자동 흡수 (plugin 작성 없이 core 가 처리)
- `code_methods.is_synthetic` 컬럼 추가 (additive migration)
- 합성기는 generated 와 직접 작성 method 를 구별 안 함 — uniform Python 처리
- v2 영향 zero
- 일반화: 알려진 processor 의 set 이 core 안에 있고, 미지의 processor 는 plugin

## 참조

- ADR-002 (plugins/<sys>/)
- ADR-006 (Case 3 annotation-based dispatch — 이 ADR 의 sibling)
- 사용자 D 선택 응답
