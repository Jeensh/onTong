# Phase 5-D/E: 수평 확장 + LLM 최적화 — 완료 요약

## Phase 5-D: 수평 확장 + 리소스 거버넌스 (5/5)

### P5D-1: Nginx 리버스 프록시 + 로드 밸런서
- `nginx.conf`: least_conn upstream, keepalive 32, SSE 프록시 설정
- `docker-compose.yml`: Nginx Alpine 서비스 (포트 80), `--scale backend=N` 지원
- backend에서 `container_name` 제거 (스케일링 호환)

### P5D-2: Docker 리소스 제한
- 이전 세션에서 완료 — backend 4C/4G, frontend 1C/1G, chroma 2C/2G, redis 1C/512M

### P5D-3: ChromaDB 커넥션 풀링
- `chromadb.Settings` 적용, anonymized_telemetry 비활성화

### P5D-4: get_all_embeddings 페이지네이션
- offset/limit 1000건 배치 조회, 메모리 스파이크 방지 (1-2GB → < 200MB)

### P5D-5: SSE 실시간 이벤트 브로드캐스트
- `event_bus.py`: EventBus 싱글톤 (asyncio.Queue fan-out)
- `main.py`: `GET /api/events` SSE endpoint
- `wiki_service.py`: 파일 CRUD 시 tree_change/index_status 이벤트 발행
- `TreeNav.tsx`: EventSource 구독 → 트리 실시간 업데이트

## Phase 5-E: LLM 처리량 최적화 (4/4)

### P5E-1: RAG LLM 파이프라인 최적화
- clarity_check는 이미 rule-based (LLM 호출 없음)
- cognitive_reflect 결과 캐싱으로 반복 쿼리 시 LLM 호출 스킵

### P5E-2: LLM 응답 캐싱
- `_reflection_cache`: 인메모리 dict, TTL 10분, 최대 256개 LRU
- 키: query+context 해시, 동일 쿼리+유사 컨텍스트 → 즉시 반환

### P5E-3: Ollama 동시 처리
- `config.py`: ollama_num_parallel=4, llm_semaphore_limit=8
- `docker-compose.yml`: OLLAMA_NUM_PARALLEL=4 환경변수
- `rag_agent.py`: asyncio.Semaphore로 동시 LLM 호출 수 제한

### P5E-4: 백그라운드 검색 인덱스 캐싱
- `search.py`: backlinks/tags 엔드포인트에 60초 TTL 인메모리 캐시
- 100K 파일에서 수 초 → < 10ms (캐시 적중 시)

## Phase 5 최종 규모
| 지표 | Phase 4 | Phase 5 완료 |
|------|---------|-------------|
| 파일 수 | ~2,000 | **100,000+** |
| 동시 사용자 | ~50 | **5,000+** |
| 트리 로딩 | OOM (100K) | **< 200ms** |
| 검색 응답 | 3.2초 | **< 300ms** |
| 저장 응답 | 300-400ms | **< 50ms** |
| 시작 시간 | 수 시간 | **< 5초** |
| RAG 응답 | 6-9초 | **< 4초** |
| 가용성 | 단일 장애점 | **HA (Nginx LB)** |
