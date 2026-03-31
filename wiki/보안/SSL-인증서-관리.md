---
domain: 보안
process: 인증서관리
tags:
  - SSL
  - 인증서
  - Let's Encrypt
  - cert-manager
status: approved
created_by: 인프라팀
updated_by: 김인증
created: "2026-02-20"
updated: "2026-03-15"
---

# SSL 인증서 관리

## 인증서 현황

| 도메인 | 발급기관 | 만료일 | 갱신 방식 | 담당 |
|--------|----------|--------|-----------|------|
| *.company.com | DigiCert | 2027-01-15 | 수동 (연간) | 인프라팀 |
| *.internal.company.com | Let's Encrypt | 자동갱신 | cert-manager | 자동 |
| api.company.com | Let's Encrypt | 자동갱신 | cert-manager | 자동 |

## cert-manager 자동 갱신

Kubernetes 환경에서는 cert-manager가 자동으로 인증서를 관리합니다:

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: api-tls
  namespace: production
spec:
  secretName: api-tls-secret
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
    - api.company.com
  renewBefore: 720h  # 만료 30일 전 자동 갱신
```

### 갱신 상태 확인

```bash
# 인증서 상태 확인
kubectl get certificates -A

# 갱신 이벤트 확인
kubectl describe certificate api-tls -n production
```

## 수동 갱신 절차 (와일드카드)

와일드카드 인증서(`*.company.com`)는 연간 수동 갱신이 필요합니다:

1. DigiCert 포털에서 갱신 요청 (만료 60일 전)
2. CSR 생성:
   ```bash
   openssl req -new -newkey rsa:2048 -nodes \
     -keyout company.key -out company.csr \
     -subj "/CN=*.company.com/O=Company Inc"
   ```
3. DigiCert에 CSR 제출 → DNS 검증
4. 발급된 인증서를 로드밸런서/CDN에 교체
5. 모니터링 알림에서 만료일 갱신 확인

## 인증서 만료 알림

[[서비스-모니터링-구성]]의 Blackbox Exporter가 30일 전부터 알림을 발송합니다:

- **30일 전**: #alerts-infra 슬랙 알림 (P3)
- **7일 전**: 담당자 직접 멘션 + 이메일 (P2)
- **1일 전**: #incident-war-room (P1)

## 관련 문서

- [[보안정책-가이드]]
- [[서비스-모니터링-구성]]
