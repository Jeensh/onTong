---
domain: 개발운영
process: 웹서버
tags:
  - Nginx
  - 리버스프록시
  - 설정
status: deprecated
superseded_by: 개발운영/Nginx-설정-가이드-v2.md
created_by: 인프라팀
updated_by: 김엔진
created: "2025-06-01"
updated: "2025-12-15"
---

# Nginx 설정 가이드 (v1)

> **이 문서는 폐기되었습니다.** 최신 버전: [[Nginx-설정-가이드-v2]]

## 기본 리버스 프록시 설정

```nginx
server {
    listen 80;
    server_name api.company.com;

    location / {
        proxy_pass http://backend:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 알려진 문제

- WebSocket 미지원
- rate limiting 미설정
- 보안 헤더 누락
