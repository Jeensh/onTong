---
domain: 개발운영
process: DB관리
tags:
  - DB
  - PostgreSQL
  - 성능
  - 슬로우쿼리
status: approved
created_by: DBA팀
updated_by: 이디비
created: "2026-02-10"
updated: "2026-03-22"
---

# DB 점검 가이드

## 일일 점검 항목

### 1. 커넥션 풀 상태

```sql
-- 현재 커넥션 수
SELECT count(*) FROM pg_stat_activity;

-- 상태별 커넥션
SELECT state, count(*)
FROM pg_stat_activity
GROUP BY state;

-- idle in transaction (5분 이상 → 문제)
SELECT pid, now() - xact_start AS duration, query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND now() - xact_start > interval '5 minutes';
```

> **기준**: 전체 커넥션이 `max_connections`의 80% 초과 시 알림

### 2. 슬로우 쿼리 확인

```sql
-- 최근 24시간 슬로우 쿼리 (>1초)
SELECT calls, mean_exec_time, query
FROM pg_stat_statements
WHERE mean_exec_time > 1000
ORDER BY mean_exec_time DESC
LIMIT 20;
```

### 3. 테이블 사이즈/블로트

```sql
-- 상위 20 테이블 크기
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
       pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS data_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 20;
```

### 4. Replication 상태

```sql
-- 리플리케이션 lag 확인
SELECT client_addr,
       pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS lag_bytes
FROM pg_stat_replication;
```

> **기준**: lag > 10MB이면 원인 파악 필요

## 주간 점검 항목

### VACUUM/ANALYZE 상태

```sql
-- 마지막 vacuum/analyze 시점
SELECT schemaname, relname,
       last_vacuum, last_autovacuum,
       last_analyze, last_autoanalyze
FROM pg_stat_user_tables
WHERE last_autovacuum IS NULL
   OR last_autovacuum < now() - interval '7 days'
ORDER BY n_dead_tup DESC
LIMIT 10;
```

### 인덱스 사용률

```sql
-- 사용되지 않는 인덱스 (제거 후보)
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND schemaname = 'public'
ORDER BY pg_relation_size(indexrelid) DESC;
```

## 긴급 상황별 대응

| 상황 | 즉시 조치 | 후속 조치 |
|------|-----------|-----------|
| 커넥션 풀 소진 | idle 커넥션 강제 종료 | 커넥션 리크 원인 파악 |
| Replication 중단 | 슬레이브 재구성 | 네트워크/디스크 점검 |
| 디스크 90% 초과 | 오래된 WAL/로그 정리 | 디스크 증설 요청 |
| 락 대기 과다 | 블로킹 세션 확인/종료 | 트랜잭션 패턴 개선 |

## 관련 문서

- [[서비스-모니터링-구성]]
- [[장애대응-플레이북]]
