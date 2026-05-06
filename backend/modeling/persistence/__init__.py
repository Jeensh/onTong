"""SQLite persistence — Section 2 modeling stores 의 영구화 어댑터.

P13 (2026-04-26) — Q1=A 결정에 따라 모든 in-memory store 를 SQLite 단일 파일로
영구화. SQLAlchemy 2.0 ORM 사용. Protocol 은 그대로 유지하므로 in-memory 어댑터도
test 용으로 keep.

DB 위치 : `data/ontology.db` (default), 환경변수 `ONTONG_DB_PATH` 로 override 가능.

설계 원칙 :
    1. **Protocol 호환** — 기존 BusinessTermRegistry / ConceptBindingStore 등 Protocol
       을 그대로 구현. main.py 의 wiring 만 바꾸면 됨.
    2. **세션 단위 commit** — store 메서드 내부에서 세션 열고 commit + rollback.
       호출자는 세션 무지.
    3. **Pydantic ↔ SQLAlchemy** — store 가 ORM row 를 Pydantic model 로 변환해서
       반환. 외부 (API / 테스트) 는 ORM row 안 보임.
    4. **마이그레이션 = Alembic** — schema 변경 추적. 첫 시드는 metadata.create_all()
       로 idempotent 부트.
"""
