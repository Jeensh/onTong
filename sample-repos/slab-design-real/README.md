# slab-design-real

> 사용자가 실제로 가져올 Slab Design 데모 소스의 destination.

## 사용법
1. 만들어온 데모 소스를 이 폴더 안에 그대로 붙여넣기 (`src/main/java/...`, `pom.xml`, `application.yml`, `README.md` 등 일반 Spring Boot 구조 그대로).
2. 12-analyzer 실행 :
   ```bash
   cd /Users/donghae/workspace/ai/onTong
   .venv/bin/python scripts/dump_entities_snapshot.py \
       --repo sample-repos/slab-design-real/src/main/java \
       --out  sample-repos/slab-design-real/.analyzed/entities.json \
       --repo-id slab-design-real
   ```
3. JPA Repository 가 있다면 READS_TABLE / WRITES_TABLE 그래프 자동 추출 (B5-7).

## sample-repos/ 구조
- `slab-design-engine/` — 합성 placeholder (의도적 gap 5종 박힘, PoC 검증 baseline). 회귀 테스트가 의존하므로 보존.
- `slab-design-real/` — **이 폴더** — 실제 데모 소스 destination.
- `scm-demo/` — 별개 SCM 데모.

## 다음 단계 (데모 코드 도착 후)
1. `dump_entities_snapshot.py` 실행 → 12-analyzer 결과 즉시 확인.
2. 매뉴얼 작성 (`wiki/공정계획/slab-설계-기준서.md` 또는 별도) → 의도적 gap 5종 트리거.
3. `POST /api/modeling/gaps/scan {"repo_id":"slab-design-real"}` 5건 후보 검증 (E1-e).
4. RuleRegistry 시드 (REPL) :
   ```python
   from pathlib import Path
   from backend.modeling.gap_detection import seed_rules_from_repo
   from backend.main import _rule_registry  # lifespan 노출 방식 따라 import 변경
   seed_rules_from_repo(
       Path('sample-repos/slab-design-real/src/main/java'),
       'slab-design-real',
       _rule_registry,
   )
   ```
