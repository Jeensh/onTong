---
domain: 인프라
process: 컨테이너운영
tags:
  - Kubernetes
  - kubectl
  - 트러블슈팅
  - 노하우
status: approved
created_by: DevOps팀
updated_by: 이컨테이너
created: "2026-01-25"
updated: "2026-03-22"
---

# Kubernetes 운영 치트시트

## 일상 운영

### Pod 상태 확인

```bash
# 전체 네임스페이스 Pod 상태
kubectl get pods -A | grep -v Running

# 특정 네임스페이스 상세
kubectl get pods -n production -o wide

# 최근 이벤트 (문제 진단에 필수)
kubectl get events -n production --sort-by='.lastTimestamp' | tail -20
```

### 로그 확인

```bash
# 단일 Pod 로그
kubectl logs <pod> -n <ns> --tail=100

# 이전 컨테이너 로그 (CrashLoopBackOff 시)
kubectl logs <pod> -n <ns> --previous

# 라벨 기반 여러 Pod 로그
kubectl logs -l app=api-server -n production --tail=50
```

### 리소스 사용량

```bash
# 노드별 리소스
kubectl top nodes

# Pod별 리소스 (네임스페이스)
kubectl top pods -n production --sort-by=memory
```

## 트러블슈팅

### CrashLoopBackOff

1. `kubectl describe pod <pod>` → Events 섹션 확인
2. `kubectl logs <pod> --previous` → 마지막 로그 확인
3. 흔한 원인:
   - OOMKilled → 메모리 limit 증가
   - 설정 파일 오류 → ConfigMap/Secret 확인
   - 의존 서비스 미접속 → 네트워크/DNS 확인

### ImagePullBackOff

1. 이미지 이름/태그 오타 확인
2. 프라이빗 레지스트리 → `imagePullSecrets` 확인
3. `kubectl describe pod` → 이미지 풀 에러 메시지 확인

### Pending Pod

1. `kubectl describe pod` → Events에서 스케줄링 실패 이유 확인
2. 흔한 원인:
   - 노드 리소스 부족 → `kubectl top nodes`
   - nodeSelector/toleration 불일치
   - PVC 바인딩 실패

### Node NotReady

```bash
# 노드 상태 확인
kubectl describe node <node-name>

# kubelet 로그 (노드 SSH 후)
journalctl -u kubelet --since "10 minutes ago"
```

## 유용한 원라이너

```bash
# 모든 네임스페이스의 비정상 Pod
kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded

# 리소스 제한 없는 Pod 찾기
kubectl get pods -A -o json | jq '.items[] | select(.spec.containers[].resources.limits == null) | .metadata.name'

# 특정 노드의 Pod 목록
kubectl get pods -A --field-selector spec.nodeName=<node>

# 모든 Ingress 목록
kubectl get ingress -A
```

## 클러스터 정보

| 환경 | 컨텍스트 | 노드 수 | 용도 |
|------|----------|---------|------|
| production | prod-k8s | 12 | 운영 |
| staging | stg-k8s | 4 | 검증 |
| dev | dev-k8s | 2 | 개발 |

## 관련 문서

- [[서비스-모니터링-구성]]
- [[배포-파이프라인-구성]]
- [[롤백-절차-가이드]]
