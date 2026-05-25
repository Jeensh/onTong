"""Replace section3 multiturn sessions with 5 realistic demo queries (live LLM).

Run: set -a && source .env && set +a && .venv/bin/python scripts/seed_section3_demo_sessions.py
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import requests


BASE = "http://localhost:8001/api/section3/multiturn"
REPO = "slab-design-real-v2"
DB = Path("data/ontology.db")

QUERIES = [
    "K-Pro 박판 신규 주문 (두께 0.1mm) 사전 검증이 어디서 거부되는지 시뮬",
    "표준 열연 슬라브 폭 자동 결정 로직 — 1240mm 주문 기준 시뮬",
    "당일 납기 + 중량 100kg 이상 + 길이 1m 미만 주문은 처리되나?",
    "신공장 P9 plant 마스터 미등록 시 누적 실수율 계산 폴백 동작?",
    "사용자 입력 오류로 슬라브 두께 -1mm 가 들어오면 어떤 에러가 표시되나?",
]


def wipe_existing() -> None:
    con = sqlite3.connect(DB)
    n_dec = con.execute("DELETE FROM section3_decision_log").rowcount
    n_sess = con.execute("DELETE FROM section3_session").rowcount
    con.commit()
    con.close()
    print(f"  wiped: decision_log {n_dec} / session {n_sess}")


def confirm_for(kind: str, payload: dict) -> dict | None:
    """Build confirm request body for given gate kind.

    Server schema: {action: 'confirm'|'modify'|'retry', user_response: {...}}
    """
    if kind == "intent_classified":
        return {"action": "confirm", "user_response": {}}
    if kind == "target_selected":
        recommended = payload.get("recommended_index")
        if recommended is None and payload.get("candidates"):
            recommended = 0
        if recommended is None:
            return None  # no candidates → can't confirm
        return {
            "action": "confirm",
            "user_response": {"selected_index": int(recommended)},
        }
    if kind == "bundle_prepared":
        return {"action": "confirm", "user_response": {}}
    return None  # terminal kinds


def run_session(query: str) -> str | None:
    print(f"\n┌─ {query}")
    r = requests.post(f"{BASE}/start", json={"repo_id": REPO, "user_query": query})
    if r.status_code != 200:
        print(f"  start failed: {r.status_code} {r.text[:200]}")
        return None
    sid = r.json()["session_id"]
    print(f"│  sid: {sid[:8]}")

    next_turn = 2
    for _ in range(8):  # safety bound
        # /respond
        r = requests.post(
            f"{BASE}/respond/{sid}",
            json={"message": query},
            timeout=60,
        )
        if r.status_code != 200:
            print(f"│  respond turn {next_turn}: {r.status_code} {r.text[:200]}")
            break
        body = r.json()
        payload = body["payload"]
        kind = payload.get("kind", "?")
        intent = payload.get("intent", "-")
        print(f"│  turn {next_turn:>2}: {kind:<22} intent={intent}")

        if kind in ("executed_simulation", "executed_hypothesis"):
            print(f"└─ ✓ done")
            return sid

        cr = confirm_for(kind, payload)
        if cr is None:
            print(f"│  cannot confirm kind={kind}, payload={list(payload.keys())[:6]}")
            break
        r = requests.post(f"{BASE}/confirm/{sid}/{next_turn}", json=cr, timeout=10)
        if r.status_code != 200:
            print(f"│  confirm turn {next_turn}: {r.status_code} {r.text[:200]}")
            break
        next_turn += 1
        time.sleep(0.5)

    print(f"└─ ✗ aborted")
    return sid


def main() -> None:
    print("== Step 1: wipe existing sessions ==")
    wipe_existing()

    print("\n== Step 2: live-run 5 demo sessions ==")
    sids = []
    for q in QUERIES:
        sid = run_session(q)
        if sid:
            sids.append(sid)
        time.sleep(1.5)  # rate limit between sessions

    print("\n== Step 3: verify recent panel ==")
    r = requests.get(f"{BASE}/sessions?limit=10&repo_id={REPO}")
    if r.status_code == 200:
        for s in r.json()["sessions"]:
            print(f"  {s['id'][:8]} | {s['status']:<6} | turn={s['turn_count']} | {s['user_query'][:60]}")
    else:
        print(f"  list failed: {r.status_code}")


if __name__ == "__main__":
    main()
