"""Section 3 simulation runner — spec 05 (`05-runner-interface.md`) 의 구현체.

모듈:
- lookup_source : LookupDataSource (fixture_only / fixture_with_db_fallback / db_snapshot 3-mode)
- python_generator : PythonGenerator (delegation tree → 실행 가능 Python)
- java_sandbox : JavaSandbox protocol + Stub/JvmSubprocess/Graalvm 3-tier
- orchestrator : Orchestrator — running 단계 entry (lookup_source + python_generator + java_sandbox 묶음)

본 모듈은 `backend.modeling.api.ontology_query` (DTO + facade) 만 read-only 로 import.
modeling 측 internal layer (mapping_layer / domain_layer / code_layer / persistence) 직접 import 금지.
"""
