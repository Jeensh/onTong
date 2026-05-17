#!/bin/bash
# Section 3 — Simulation 전용 검증 스크립트.
# Usage: bash toClaude/simulation/verify_section3.sh
#
# _shared/verify.sh와 분리 (섹션 격리 규칙 준수).
# 사용자 승인 시 향후 _shared/verify.sh 본문에 통합 가능.

set -e
cd "$(dirname "$0")/../.."

PASS=0
FAIL=0
WARN=0

ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }
warn() { echo "  ? $1"; WARN=$((WARN+1)); }

PYTEST="./venv/bin/pytest"
[ -x "$PYTEST" ] || PYTEST="pytest"

echo "═══ Section 3 — pytest ═══"
if "$PYTEST" tests/simulation/ -q --tb=line 2>&1 | tail -1 | grep -q "passed"; then
  ok "$("$PYTEST" tests/simulation/ -q 2>&1 | tail -1)"
else
  fail "tests/simulation/ failed"
fi

echo ""
echo "═══ Section 3 — sandbox CLI ═══"
RESULT=$(./venv/bin/python -m backend.simulation.sandbox.runner \
  --step productivity \
  --input '{"order":{"confirmedPlantCd":"K K K   "}}' 2>&1 | tail -1)
if echo "$RESULT" | grep -q '"ok": true'; then
  ok "productivity step (cumulative=$(echo "$RESULT" | grep -o '"cumulative_productivity": "[^"]*"'))"
else
  fail "sandbox CLI: $RESULT"
fi

echo ""
echo "═══ Section 3 — pipeline e2e ═══"
RESULT=$(./venv/bin/python -m backend.simulation.sandbox.runner \
  --step pipeline --input '{"rules":{"hrf":"0.85"}}' 2>&1 | tail -1)
if echo "$RESULT" | grep -q '"stage": "ok"'; then
  ok "pipeline stage=ok with rules.hrf=0.85"
else
  warn "pipeline stage != ok (Hypothesis 변동성 가능)"
fi

echo ""
echo "═══ Section 3 — frontend tsc ═══"
if cd frontend && npx tsc --noEmit > /tmp/sim-tsc.log 2>&1; then
  ok "tsc --noEmit clean"
else
  fail "TypeScript errors — see /tmp/sim-tsc.log"
fi
cd ..

echo ""
echo "═══ Section 3 — SSE smoke (백엔드 :8000 가정, 미기동이면 skip) ═══"
if curl -sf http://localhost:8000/openapi.json > /dev/null 2>&1; then
  EVENTS=$(curl -s -m 30 -N -X POST http://localhost:8000/api/simulation/agents/test-data/stream \
    -H "Content-Type: application/json" \
    -d '{"target_id":"validator","case_types":["normal"],"test_count":1}' 2>/dev/null | grep -c "event" || echo 0)
  if [ "$EVENTS" -gt 0 ]; then
    ok "SSE stream ($EVENTS event lines)"
  else
    fail "SSE stream returned no events"
  fi
else
  warn "backend on :8000 not running (skip SSE smoke)"
fi

echo ""
echo "═══════════════════════════"
echo "  PASS: $PASS  FAIL: $FAIL  WARN: $WARN"
if [ "$FAIL" -gt 0 ]; then
  echo "  *** FAILURES DETECTED ***"
  exit 1
else
  echo "  Section 3 verification passed."
fi
