"""Create realistic test images + wiki documents for image search demo.

Usage:
    cd /Users/donghae/workspace/ai/onTong
    .venv/bin/python scripts/create_image_test_data.py

Creates:
    wiki/assets/  — 6 PNG images with Korean text
    wiki/인프라/   — 2 new documents referencing the images
    wiki/SCM/     — 1 new document referencing the images
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont

WIKI_DIR = Path(__file__).resolve().parent.parent / "wiki"
ASSETS_DIR = WIKI_DIR / "assets"


def draw_text_block(img: Image.Image, lines: list[str], start_y: int = 20, font_size: int = 16, color: str = "black") -> None:
    """Draw multiple lines of text on an image."""
    draw = ImageDraw.Draw(img)
    y = start_y
    for line in lines:
        draw.text((20, y), line, fill=color)
        y += font_size + 8


def create_error_screenshot() -> Path:
    """500 error screen — server error page."""
    img = Image.new("RGB", (600, 400), color="#1a1a2e")
    draw = ImageDraw.Draw(img)

    # Header bar
    draw.rectangle([(0, 0), (600, 50)], fill="#e94560")
    draw.text((20, 15), "ERROR - Internal Server Error", fill="white")

    # Error content
    lines = [
        "HTTP 500 Internal Server Error",
        "",
        "Timestamp: 2026-04-15 14:32:17 KST",
        "Request: POST /api/payment/process",
        "Server: prod-web-03.example.com",
        "",
        "Error Details:",
        "  java.lang.NullPointerException",
        "  at PaymentService.processOrder(PaymentService.java:142)",
        "  at PaymentController.checkout(PaymentController.java:87)",
        "  at RequestHandler.handle(RequestHandler.java:203)",
        "",
        "Transaction ID: TXN-20260415-00847",
        "User Session: sess_kOO_manager_2026",
        "Amount: 1,250,000 KRW",
    ]
    draw_text_block(img, lines, start_y=70, color="#ffffff")

    path = ASSETS_DIR / "error-500-payment.png"
    img.save(path)
    return path


def create_chat_capture_1() -> Path:
    """KakaoTalk-style chat capture — customer reporting payment failure."""
    img = Image.new("RGB", (500, 500), color="#b2c7d9")
    draw = ImageDraw.Draw(img)

    # Chat header
    draw.rectangle([(0, 0), (500, 45)], fill="#3b1e54")
    draw.text((20, 12), "KakaoTalk - CS Support Channel", fill="white")

    messages = [
        (True,  "14:28", "Kim OO (Customer)",  "Payment failed again"),
        (True,  "14:28", "Kim OO",             "I clicked checkout button"),
        (True,  "14:29", "Kim OO",             "500 server error message appeared"),
        (False, "14:30", "Park OO (CS Team)",   "Which product were you purchasing?"),
        (True,  "14:31", "Kim OO",             "Order #20260415-00847"),
        (True,  "14:31", "Kim OO",             "Amount was 1,250,000 won"),
        (False, "14:32", "Park OO",            "Checking with dev team now"),
        (False, "14:35", "Park OO",            "Issue confirmed. Server error on prod-web-03"),
        (False, "14:36", "Park OO",            "Dev team is deploying hotfix"),
    ]

    y = 60
    for is_left, time, sender, text in messages:
        bg = "#ffffff" if is_left else "#fee500"
        x = 20 if is_left else 200
        w = 270

        draw.rectangle([(x, y), (x + w, y + 40)], fill=bg, outline="#cccccc")
        draw.text((x + 10, y + 3), f"{sender} [{time}]", fill="#666666")
        draw.text((x + 10, y + 20), text, fill="#000000")
        y += 48

    path = ASSETS_DIR / "chat-payment-failure.png"
    img.save(path)
    return path


def create_chat_capture_2() -> Path:
    """Slack-style chat — dev team discussing the fix."""
    img = Image.new("RGB", (550, 400), color="#ffffff")
    draw = ImageDraw.Draw(img)

    # Slack header
    draw.rectangle([(0, 0), (550, 40)], fill="#4a154b")
    draw.text((20, 10), "#dev-incident  |  Payment Service Down", fill="white")

    messages = [
        ("14:33", "Lee DevOps",    "prod-web-03 payment endpoint returning 500"),
        ("14:34", "Choi Backend",  "NullPointerException in PaymentService.java:142"),
        ("14:34", "Choi Backend",  "Root cause: null check missing on couponDiscount field"),
        ("14:36", "Choi Backend",  "Hotfix PR #2847 created. Adding null guard."),
        ("14:38", "Lee DevOps",    "Deployed hotfix to prod. Monitoring..."),
        ("14:42", "Lee DevOps",    "Payment success rate back to 99.8%. Resolved."),
        ("14:45", "Park CS",       "Customer Kim OO confirmed payment went through"),
    ]

    y = 55
    for time, sender, text in messages:
        draw.text((20, y), f"[{time}]", fill="#999999")
        draw.text((80, y), sender, fill="#1264a3")
        draw.text((80, y + 18), text, fill="#333333")
        y += 45

    path = ASSETS_DIR / "slack-dev-incident.png"
    img.save(path)
    return path


def create_monitoring_dashboard() -> Path:
    """Grafana-style monitoring dashboard showing error spike."""
    img = Image.new("RGB", (700, 400), color="#181b1f")
    draw = ImageDraw.Draw(img)

    # Header
    draw.text((20, 10), "Grafana Dashboard: Payment Service Health", fill="#fb8b24")
    draw.text((20, 30), "2026-04-15  14:00 ~ 15:00 KST", fill="#999999")

    # Fake graph area
    draw.rectangle([(20, 60), (680, 250)], outline="#333333")
    draw.text((25, 65), "Error Rate (%)", fill="#ff6b6b")

    # Draw a spike pattern
    points = [(20, 240)] + [(20 + i * 10, 240) for i in range(28)]
    # Spike at 14:30
    for i in range(28, 35):
        points.append((20 + i * 10, 240 - (i - 28) * 25))
    for i in range(35, 42):
        points.append((20 + i * 10, 240 - (42 - i) * 25))
    for i in range(42, 66):
        points.append((20 + i * 10, 240))
    for i in range(len(points) - 1):
        draw.line([points[i], points[i + 1]], fill="#ff6b6b", width=2)

    # Annotations
    draw.text((300, 100), "14:30 Error spike", fill="#ff6b6b")
    draw.text((300, 120), "Peak: 47.3% error rate", fill="#ff6b6b")
    draw.text((440, 160), "14:38 Hotfix deployed", fill="#50fa7b")
    draw.text((540, 180), "14:42 Recovered", fill="#50fa7b")

    # Stats panel
    draw.rectangle([(20, 270), (340, 390)], outline="#333333")
    stats = [
        "Affected Transactions: 23",
        "Failed Amount: 28,750,000 KRW",
        "MTTR: 10 min (14:32 ~ 14:42)",
        "Root Cause: NullPointerException",
        "Fix: PR #2847 (null guard)",
    ]
    draw_text_block(img, stats, start_y=280, color="#cccccc")

    # Server info
    draw.rectangle([(360, 270), (680, 390)], outline="#333333")
    server_info = [
        "Server: prod-web-03",
        "Service: payment-api v3.2.1",
        "JVM Heap: 82% (warning)",
        "Active Connections: 1,247",
        "Avg Response: 2,340ms (degraded)",
    ]
    draw_text_block(img, server_info, start_y=280, color="#cccccc")

    path = ASSETS_DIR / "monitoring-payment-error.png"
    img.save(path)
    return path


def create_scm_order_screenshot() -> Path:
    """SCM system order screen with Korean text."""
    img = Image.new("RGB", (600, 350), color="#f5f5f5")
    draw = ImageDraw.Draw(img)

    # Header
    draw.rectangle([(0, 0), (600, 40)], fill="#1976d2")
    draw.text((20, 10), "SCM System - Order Management", fill="white")

    # Table header
    draw.rectangle([(20, 55), (580, 80)], fill="#e3f2fd")
    headers = ["Order ID", "Product", "Qty", "Status", "Due Date"]
    x_positions = [30, 130, 300, 370, 480]
    for x, h in zip(x_positions, headers):
        draw.text((x, 60), h, fill="#333333")

    # Table rows
    rows = [
        ["ORD-2026-1847", "Semiconductor Chip A1", "5,000", "DELAYED", "2026-04-20"],
        ["ORD-2026-1848", "PCB Board Type-C", "2,500", "ON TRACK", "2026-04-18"],
        ["ORD-2026-1849", "Battery Module BM-7", "1,200", "CRITICAL", "2026-04-16"],
        ["ORD-2026-1850", "Display Panel 15.6", "800", "ON TRACK", "2026-04-22"],
        ["ORD-2026-1851", "Memory DDR5 16GB", "10,000", "DELAYED", "2026-04-19"],
    ]

    y = 90
    for row in rows:
        status_color = "#f44336" if row[3] in ("DELAYED", "CRITICAL") else "#4caf50"
        for x, val in zip(x_positions, row):
            color = status_color if val in ("DELAYED", "CRITICAL") else "#333333"
            draw.text((x, y), val, fill=color)
        y += 30

    # Summary
    draw.rectangle([(20, 260), (580, 340)], fill="#fff3e0")
    summary = [
        "Summary: 5 active orders, 2 DELAYED, 1 CRITICAL",
        "Total value: 4,850,000,000 KRW",
        "Critical: ORD-2026-1849 Battery Module due TOMORROW",
    ]
    draw_text_block(img, summary, start_y=270, color="#e65100")

    path = ASSETS_DIR / "scm-order-status.png"
    img.save(path)
    return path


def create_terminal_log() -> Path:
    """Server terminal log showing the error."""
    img = Image.new("RGB", (700, 350), color="#0c0c0c")
    draw = ImageDraw.Draw(img)

    lines = [
        ("green",  "donghae@prod-web-03:~$ tail -f /var/log/payment-api/error.log"),
        ("white",  ""),
        ("red",    "2026-04-15 14:30:12.847 ERROR [payment-api] PaymentService:142"),
        ("red",    "  java.lang.NullPointerException: couponDiscount is null"),
        ("gray",   "  at c.e.payment.PaymentService.processOrder(PaymentService.java:142)"),
        ("gray",   "  at c.e.payment.PaymentController.checkout(PaymentController.java:87)"),
        ("white",  ""),
        ("red",    "2026-04-15 14:30:13.102 ERROR [payment-api] PaymentService:142"),
        ("red",    "  java.lang.NullPointerException: couponDiscount is null"),
        ("white",  ""),
        ("yellow", "2026-04-15 14:30:15.203 WARN  [payment-api] CircuitBreaker OPEN"),
        ("yellow", "  Payment endpoint circuit breaker opened after 5 failures"),
        ("white",  ""),
        ("green",  "2026-04-15 14:38:44.001 INFO  [payment-api] Deployment v3.2.2 started"),
        ("green",  "2026-04-15 14:39:01.337 INFO  [payment-api] Health check passed"),
        ("green",  "2026-04-15 14:39:02.100 INFO  [payment-api] CircuitBreaker CLOSED"),
    ]

    color_map = {
        "green": "#50fa7b", "red": "#ff5555", "yellow": "#f1fa8c",
        "gray": "#6272a4", "white": "#f8f8f2",
    }

    y = 10
    for color_name, text in lines:
        draw.text((10, y), text, fill=color_map[color_name])
        y += 20

    path = ASSETS_DIR / "terminal-payment-error-log.png"
    img.save(path)
    return path


def create_wiki_documents():
    """Create wiki .md documents that reference the test images."""

    # Document 1: Payment incident report (image-heavy)
    doc1 = """\
---
domain: 인프라
process: 장애대응
tags:
  - 결제
  - 서버에러
  - 장애보고
status: approved
created: "2026-04-15"
updated: "2026-04-15"
created_by: park_cs
---
# 2026-04-15 결제 서비스 장애 보고

## 장애 개요

2026년 4월 15일 14:30경 결제 서비스(prod-web-03)에서 HTTP 500 에러가 발생하여 약 10분간 결제 기능이 중단됨.

## 고객 문의 (김OO 매니저)

아래는 CS 채널에서 접수된 최초 문의 내용입니다.

![고객 채팅](assets/chat-payment-failure.png)

## 에러 화면

고객이 결제 시 확인한 에러 화면:

![500 에러](assets/error-500-payment.png)

## 개발팀 대응

Slack #dev-incident 채널에서의 대응 과정:

![개발팀 슬랙](assets/slack-dev-incident.png)

## 서버 로그

prod-web-03 서버의 에러 로그:

![서버 로그](assets/terminal-payment-error-log.png)

## 모니터링 대시보드

Grafana 대시보드에서 확인된 에러율 스파이크:

![모니터링](assets/monitoring-payment-error.png)

## 조치 결과

- **원인**: PaymentService.java:142에서 couponDiscount 필드 null 체크 누락
- **조치**: PR #2847 핫픽스 배포 (null guard 추가)
- **복구 시간**: 14:42 (MTTR 10분)
- **영향**: 거래 23건, 총 28,750,000원
- **재발 방지**: coupon 관련 필드 전수 null 체크 + 단위 테스트 추가 예정
"""
    doc1_path = WIKI_DIR / "인프라" / "결제-서비스-장애보고-20260415.md"
    doc1_path.write_text(doc1, encoding="utf-8")
    print(f"Created: {doc1_path}")

    # Document 2: SCM order delay report (image-only style)
    doc2 = """\
---
domain: SCM
process: 주문관리
tags:
  - 납기지연
  - 주문현황
  - 긴급
status: draft
created: "2026-04-16"
updated: "2026-04-16"
created_by: lee_scm
---
# SCM 주문 납기 지연 현황 (2026-04-16)

## 현재 주문 상태

![주문 현황](assets/scm-order-status.png)

## 긴급 조치 필요

ORD-2026-1849 Battery Module BM-7이 내일 납기인데 CRITICAL 상태. 즉시 대응 필요.
"""
    doc2_path = WIKI_DIR / "SCM" / "주문-납기지연-현황-20260416.md"
    doc2_path.write_text(doc2, encoding="utf-8")
    print(f"Created: {doc2_path}")


def main():
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    print("=== Creating test images ===")
    paths = [
        ("Error screenshot", create_error_screenshot()),
        ("Chat capture 1", create_chat_capture_1()),
        ("Chat capture 2 (Slack)", create_chat_capture_2()),
        ("Monitoring dashboard", create_monitoring_dashboard()),
        ("SCM order screen", create_scm_order_screenshot()),
        ("Terminal error log", create_terminal_log()),
    ]

    for name, path in paths:
        print(f"  Created: {path.name} ({path.stat().st_size // 1024}KB) — {name}")

    print("\n=== Creating wiki documents ===")
    create_wiki_documents()

    print(f"\n=== Done ===")
    print(f"Images: {len(paths)} files in wiki/assets/")
    print(f"Documents: 2 new wiki pages referencing the images")
    print(f"\nNext steps:")
    print(f"  1. Run OCR:     .venv/bin/python -m backend.cli.backfill_images --ocr-only")
    print(f"  2. Check sidecar: cat wiki/assets/error-500-payment.png.meta.json | python3 -m json.tool")
    print(f"  3. Reindex:     curl -X POST http://localhost:8001/api/wiki/reindex")
    print(f"  4. Search test: curl 'http://localhost:8001/api/search?q=결제+에러+500'")


if __name__ == "__main__":
    main()
