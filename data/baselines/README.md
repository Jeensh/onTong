# Section 3 — Java Baseline 파일 (Sprint 2)

`sim_v2_bridge.load_baseline_map(method_fqn)` 가 읽는 디렉토리.

## 파일명 규칙
- method_fqn 의 `.`, `(`, `)`, `,` 를 `_` 로 치환한 이름 + `.json`
- 예) `com.x.Foo.bar(int,String)` → `com_x_Foo_bar_int_String_.json`

## JSON 구조
```json
[
  { "args": [self_value, arg0, arg1, ...], "expected": <any> }
]
```
- `args[0]` 은 self (instance 메서드라 None 가능, static 이면 첫 인자)
- `expected` 와 actual 이 일치하면 `BehaviorTwinRunner` 가 PASS 판정

## 활성화 조건
- 본 디렉토리에 해당 method 의 JSON 이 있으면 sandbox_agent 가 자동 oracle 경로 사용
- 없으면 W72 invariant 경로 (Sprint 1 default)

## 알려진 한계
- W74 stub 이 `MagicMock` 반환 시 `BehaviorTwinRunner` 가 ERROR (UC40 의 FAIL_RETURN_TYPE)
- typed-return stub 후속 작업 전까지는 baseline 이 의도한 대로 동작 안 할 수 있음
