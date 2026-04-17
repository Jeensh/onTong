# Image Search 데모 테스트 시나리오

> **목적**: 이미지 분석 파이프라인이 실제로 동작하는지 end-to-end 검증
> **사전 조건**: 테스트 데이터 이미 생성 완료 (`scripts/create_image_test_data.py`)
> **소요 시간**: ~10분

---

## 0. 테스트 데이터 확인

생성된 파일들:

| 파일 | 내용 | 크기 |
|------|------|------|
| `wiki/assets/error-500-payment.png` | HTTP 500 에러 화면 (결제 서비스) | 21KB |
| `wiki/assets/chat-payment-failure.png` | 카카오톡 CS 채팅 (김OO 고객 문의) | 24KB |
| `wiki/assets/slack-dev-incident.png` | Slack 개발팀 장애 대응 대화 | 24KB |
| `wiki/assets/monitoring-payment-error.png` | Grafana 대시보드 (에러율 스파이크) | 23KB |
| `wiki/assets/scm-order-status.png` | SCM 주문 현황 화면 (납기 지연) | 25KB |
| `wiki/assets/terminal-payment-error-log.png` | 서버 터미널 에러 로그 | 30KB |

문서 2건:
- `wiki/인프라/결제-서비스-장애보고-20260415.md` — 이미지 5개 참조 (장애 보고서)
- `wiki/SCM/주문-납기지연-현황-20260416.md` — 이미지 1개 참조 (주문 현황)

---

## 1. Sidecar 파일 확인 (OCR 결과)

OCR backfill은 이미 완료 상태. sidecar 파일 확인:

```bash
# sidecar 파일 목록
ls wiki/assets/*.meta.json

# 특정 sidecar 내용 보기
cat wiki/assets/error-500-payment.png.meta.json | python3 -m json.tool
```

**확인 포인트**:
- [  ] 6개 `.meta.json` 파일 존재
- [  ] 각 파일에 `ocr_text` 필드가 비어있지 않음
- [  ] `description` 필드는 빈 문자열 (vision_provider=none이므로 정상)
- [  ] `ocr_engine`이 "easyocr"
- [  ] `processed_at` 타임스탬프 존재

---

## 2. 서버 기동 + 재인덱싱

```bash
# 터미널 1: 서비스 실행
docker compose up -d chroma redis
cd /Users/donghae/workspace/ai/onTong
source .venv/bin/activate && set -a && source .env && set +a
uvicorn backend.main:app --host 0.0.0.0 --port 8001

# 터미널 2: 재인덱싱 (이미지 설명이 청크에 주입되도록)
curl -s -X POST http://localhost:8001/api/wiki/reindex | python3 -m json.tool
```

**확인 포인트**:
- [  ] 서버 기동 로그에 `Image analysis: OCR=easyocr, Vision=none/llava:13b` 출력
- [  ] reindex 응답에 인덱싱된 청크 수 표시

---

## 3. 검색 테스트 — 이미지 속 키워드로 문서 찾기

### 3-A. 결제 에러 관련 검색

```bash
# "PaymentService" — 에러 스크린샷/로그에만 있는 텍스트
curl -s "http://localhost:8001/api/search?q=PaymentService+500" | python3 -m json.tool | head -30

# "NullPointerException" — 터미널 로그/슬랙 대화에 있음
curl -s "http://localhost:8001/api/search?q=NullPointerException" | python3 -m json.tool | head -30

# "TXN-20260415" — 에러 화면에만 있는 트랜잭션 ID
curl -s "http://localhost:8001/api/search?q=TXN-20260415" | python3 -m json.tool | head -30
```

**확인 포인트**:
- [  ] `결제-서비스-장애보고-20260415.md` 문서가 검색 결과에 포함됨
- [  ] 검색 결과의 chunk content에 `[이미지 텍스트: ...]` 형태로 OCR 텍스트 포함

### 3-B. SCM 주문 관련 검색

```bash
# "DELAYED" — SCM 주문 화면에만 있는 상태값
curl -s "http://localhost:8001/api/search?q=DELAYED+order" | python3 -m json.tool | head -30

# "Battery Module" — 주문 화면의 상품명
curl -s "http://localhost:8001/api/search?q=Battery+Module+BM-7" | python3 -m json.tool | head -30
```

**확인 포인트**:
- [  ] `주문-납기지연-현황-20260416.md` 문서가 검색 결과에 포함됨

### 3-C. 한국어 키워드 검색 (문서 본문 + 이미지 OCR 혼합)

```bash
# "결제 장애" — 문서 본문 텍스트
curl -s "http://localhost:8001/api/search?q=결제+장애+보고" | python3 -m json.tool | head -30

# "납기 지연" — 문서 본문
curl -s "http://localhost:8001/api/search?q=납기+지연+긴급" | python3 -m json.tool | head -30
```

---

## 4. onTalk 에이전트 테스트 — 이미지 내용으로 질문

브라우저에서 `http://localhost:3000` 접속 → onTalk 채팅 열기

### 질문 1: 에러 코드로 문서 찾기
```
지난주 결제 관련 서버 에러 보고서가 있었는데?
```
**기대**: `결제-서비스-장애보고-20260415.md`를 소스로 인용하며, 장애 내용 요약

### 질문 2: 이미지 속 구체적 정보
```
PaymentService NullPointerException이 발생한 장애 건 알려줘
```
**기대**: 이미지 OCR에서 추출된 에러 내용 기반으로 해당 문서 검색됨

### 질문 3: SCM 주문 현황
```
납기 지연된 주문 현황 문서 있어?
```
**기대**: `주문-납기지연-현황-20260416.md` 검색, Battery Module BM-7 긴급 언급

### 질문 4: 이미지만 있는 정보
```
prod-web-03 서버 장애 관련 기록 찾아줘
```
**기대**: 에러 화면/모니터링/터미널 로그 이미지에서 추출된 "prod-web-03" 키워드로 문서 검색

---

## 5. 청크 내용 직접 확인 (디버깅용)

인덱싱된 청크에 이미지 설명이 실제로 포함되었는지 확인:

```bash
# ChromaDB에서 직접 검색
curl -s "http://localhost:8001/api/search?q=PaymentService&limit=3" | \
  python3 -c "
import sys, json
data = json.load(sys.stdin)
for r in data.get('results', [])[:3]:
    print(f\"=== {r.get('file_path', 'unknown')} (score: {r.get('score', 0):.3f}) ===\")
    content = r.get('content', '')
    if '[이미지' in content:
        # 이미지 텍스트가 포함된 부분만 출력
        for line in content.split('\n'):
            if '이미지' in line:
                print(f'  >> {line.strip()[:200]}')
    print()
"
```

**확인 포인트**:
- [  ] 청크 content에 `[이미지 텍스트: ...]` 블록이 포함됨
- [  ] 원본 `![](assets/...)` 마크다운은 치환되어 없음

---

## 6. (선택) Vision LLM 테스트

Ollama가 설치되어 있고 LLaVA 모델이 있으면:

```bash
# Ollama + LLaVA 설치
brew install ollama
ollama pull llava:13b

# .env에 Vision 설정 추가
echo "IMAGE_VISION_PROVIDER=ollama" >> .env
echo "IMAGE_VISION_MODEL=llava:13b" >> .env

# 기존 sidecar 재처리 (Vision 설명 생성)
.venv/bin/python -m backend.cli.backfill_images --reprocess --workers 2

# 결과 확인 — description 필드가 채워졌는지
cat wiki/assets/error-500-payment.png.meta.json | python3 -m json.tool
```

**확인 포인트**:
- [  ] `description` 필드에 한국어 맥락 설명이 생성됨
- [  ] reindex 후 검색 품질이 OCR-only 대비 향상

---

## 테스트 결과 기록

| # | 시나리오 | 결과 | 비고 |
|---|---------|------|------|
| 1 | Sidecar 파일 생성 | | |
| 2 | 서버 기동 + 재인덱싱 | | |
| 3-A | 결제 에러 키워드 검색 | | |
| 3-B | SCM 주문 키워드 검색 | | |
| 3-C | 한국어 키워드 검색 | | |
| 4-1 | onTalk: 결제 에러 보고서 | | |
| 4-2 | onTalk: NullPointerException | | |
| 4-3 | onTalk: 납기 지연 주문 | | |
| 4-4 | onTalk: prod-web-03 장애 | | |
| 5 | 청크 내 이미지 텍스트 확인 | | |
| 6 | Vision LLM (선택) | | |

---

## 정리 (테스트 후)

테스트 데이터를 유지하고 싶으면 그대로 두면 됩니다.
삭제하려면:

```bash
# 이미지 + sidecar 삭제
rm wiki/assets/error-500-payment.png*
rm wiki/assets/chat-payment-failure.png*
rm wiki/assets/slack-dev-incident.png*
rm wiki/assets/monitoring-payment-error.png*
rm wiki/assets/scm-order-status.png*
rm wiki/assets/terminal-payment-error-log.png*

# 테스트 문서 삭제
rm wiki/인프라/결제-서비스-장애보고-20260415.md
rm wiki/SCM/주문-납기지연-현황-20260416.md

# 재인덱싱
curl -X POST http://localhost:8001/api/wiki/reindex
```
