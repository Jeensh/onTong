---
domain: 개발운영
process: 캐시관리
tags:
  - Redis
  - 캐시
  - 트러블슈팅
  - 노하우
status: approved
created_by: 백엔드팀
updated_by: 최캐시
created: "2026-02-15"
updated: "2026-03-18"
---

# Redis 운영 노하우

## 클러스터 구성

| 환경 | 구성 | 메모리 | 용도 |
|------|------|--------|------|
| production | 6노드 클러스터 (3M+3S) | 64GB | 세션, 캐시, Rate limit |
| staging | Sentinel (1M+2S) | 8GB | 검증 |
| dev | Standalone | 2GB | 개발 |

## 핵심 모니터링 지표

| 지표 | 정상 범위 | 위험 기준 |
|------|-----------|-----------|
| `used_memory` | maxmemory의 70% 이하 | > 85% |
| `connected_clients` | < 5,000 | > 8,000 |
| `keyspace_hits / (hits+misses)` | > 90% | < 80% |
| `instantaneous_ops_per_sec` | < 100,000 | > 150,000 |
| `blocked_clients` | 0 | > 10 |

## 자주 겪는 문제와 해결

### 메모리 급증

```bash
# 큰 키 찾기
redis-cli --bigkeys

# 메모리 사용 상세
redis-cli info memory

# 특정 키 메모리 사용량
redis-cli memory usage <key>
```

**흔한 원인:**
- TTL 없는 키 누적 → 키 생성 시 반드시 `EX` 설정
- 큰 Hash/Set → 분할 저장
- 메모리 단편화 → `activedefrag yes` 설정

### 연결 수 폭증

```bash
# 클라이언트 목록
redis-cli client list

# idle 시간이 긴 클라이언트 확인
redis-cli client list | awk -F' ' '{for(i=1;i<=NF;i++) if($i~/^idle=/) print $i, $0}' | sort -t= -k2 -rn | head
```

**흔한 원인:**
- 커넥션 풀 미사용 → 앱에서 풀 설정 확인
- 커넥션 리크 → 예외 발생 시 미반환

### SLOWLOG 확인

```bash
# 느린 명령어 확인
redis-cli slowlog get 10

# 설정 (10ms 이상 기록)
redis-cli config set slowlog-log-slower-than 10000
```

**주의해야 할 명령어:**
- `KEYS *` → 운영에서 **절대 사용 금지** (`SCAN` 사용)
- `FLUSHALL` / `FLUSHDB` → 운영 금지
- `SMEMBERS` (대용량 Set) → `SSCAN` 사용

## 키 네이밍 컨벤션

```
{서비스}:{엔티티}:{ID}:{필드}
```

예시:
- `order:cart:user123` — 장바구니
- `auth:session:abc123` — 세션
- `cache:product:456:detail` — 상품 상세 캐시

## 백업 정책

- RDB 스냅샷: 1시간마다
- AOF: `appendfsync everysec`
- S3 백업: 일 1회 (7일 보관)

## 관련 문서

- [[서비스-모니터링-구성]]
- [[장애대응-플레이북]]
