---
domain: 개발운영
process: 웹서버
supersedes: 개발운영/Nginx-설정-가이드-v1.md
created_by: 인프라팀
updated_by: 개발자
created: '"2026-01-10"'
updated: '2026-04-01T02:15:56Z'
tags:
  - Nginx
  - 리버스프록시
  - 설정
  - WebSocket
  - 보안
---
# Nginx 설정 가이드 (v2)

> 이전 버전: [[Nginx-설정-가이드-v1]] (폐기됨)

## 표준 리버스 프록시 설정

`upstream backend {   least_conn;   server backend-1:8080;   server backend-2:8080;   server backend-3:8080;   }      server {   listen 443 ssl http2;   server_name api.company.com;      # SSL   ssl_certificate /etc/nginx/certs/api.crt;   ssl_certificate_key /etc/nginx/certs/api.key;   ssl_protocols TLSv1.2 TLSv1.3;      # 보안 헤더   add_header X-Frame-Options DENY;   add_header X-Content-Type-Options nosniff;   add_header X-XSS-Protection "1; mode=block";   add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";      # Rate Limiting   limit_req zone=api burst=20 nodelay;      # API 프록시   location /api/ {   proxy_pass http://backend;   proxy_set_header Host $host;   proxy_set_header X-Real-IP $remote_addr;   proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;   proxy_set_header X-Forwarded-Proto $scheme;      # 타임아웃   proxy_connect_timeout 10s;   proxy_read_timeout 30s;   proxy_send_timeout 30s;   }      # WebSocket 지원   location /ws/ {   proxy_pass http://backend;   proxy_http_version 1.1;   proxy_set_header Upgrade $http_upgrade;   proxy_set_header Connection "upgrade";   proxy_read_timeout 86400s;   }      # 헬스체크 (모니터링용)   location /health {   access_log off;   return 200 "OK";   }   }      # Rate limit zone 정의   limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;      # HTTP → HTTPS 리다이렉트   server {   listen 80;   server_name api.company.com;   return 301 https://$host$request_uri;   }   `

## v1 대비 변경사항

| 항목 | v1 | v2 |
| --- | --- | --- |
| SSL/TLS | 미설정 | TLS 1.2/1.3 강제 |
| 보안 헤더 | 없음 | HSTS, X-Frame 등 |
| Rate Limiting | 없음 | IP당 10 req/s |
| WebSocket | 미지원 | /ws/ 경로 지원 |
| 로드밸런싱 | 없음 | least_conn 3노드 |
| HTTP/2 | 미지원 | 지원 |

## 관련 문서

-   [[보안정책-가이드]]
    
-   [[SSL-인증서-관리]]
    
-   [[서비스-모니터링-구성]]