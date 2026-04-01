#!/bin/bash
# toClaude/verify.sh — Pre-Demo Quick Verification
# Usage: bash toClaude/verify.sh
set -e
cd "$(dirname "$0")/.."

PASS=0
FAIL=0
WARN=0

ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }
warn() { echo "  ? $1"; WARN=$((WARN+1)); }

echo "═══ 1. pytest ═══"
if ./venv/bin/pytest tests/ -x -q 2>&1 | tail -1 | grep -q "passed"; then
  ok "$(./venv/bin/pytest tests/ -x -q 2>&1 | tail -1)"
else
  fail "pytest failed"
fi

echo ""
echo "═══ 2. TypeScript ═══"
if cd frontend && npx tsc --noEmit 2>&1; then
  ok "tsc --noEmit clean"
else
  fail "TypeScript errors"
fi
cd ..

echo ""
echo "═══ 3. Backend alive ═══"
if curl -sf http://localhost:8001/api/wiki/tree > /dev/null 2>&1; then
  ok "backend responding"
else
  fail "backend not running on :8001"
fi

echo ""
echo "═══ 4. Chat basic ═══"
DELTAS=$(curl -s -m 30 -N -X POST http://localhost:8001/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"장애 대응 절차","session_id":"verify-smoke"}' 2>/dev/null | grep -c "content_delta" || echo 0)
if [ "$DELTAS" -gt 0 ]; then
  ok "chat works ($DELTAS deltas)"
else
  fail "no content_delta from chat"
fi

echo ""
echo "═══ 5. Conflict false-positive ═══"
FP_RAW=$(curl -s -m 30 -N -X POST http://localhost:8001/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"밥 맛있게 짓는법 알려줘","session_id":"verify-fp-'"$$"'"}' 2>/dev/null)
FP=$(echo "$FP_RAW" | grep -c "conflict_warning" || true)
if [ "$FP" -eq 0 ] 2>/dev/null; then
  ok "no false positive"
else
  fail "false positive conflict detected ($FP)"
fi

echo ""
echo "═══ 6. Conflict detection ═══"
CD_RAW=$(curl -s -m 30 -N -X POST http://localhost:8001/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"밥 짓는법 쌀 몇컵?","session_id":"verify-cd-'"$$"'"}' 2>/dev/null)
CD=$(echo "$CD_RAW" | grep -c "conflict_warning" || true)
if [ "$CD" -gt 0 ] 2>/dev/null; then
  ok "conflict detected"
else
  warn "conflict not detected (LLM dependent)"
fi

echo ""
echo "═══ 7. API endpoints ═══"
for ep in \
  "conflict/duplicates?threshold=0.9" \
  "metadata/tags" \
  "skills/" \
  "wiki/tree" \
  "search/quick?q=test&limit=1"
do
  if curl -sf "http://localhost:8001/api/$ep" > /dev/null 2>&1; then
    ok "$ep"
  else
    fail "$ep"
  fi
done

echo ""
echo "═══════════════════════════"
echo "  PASS: $PASS  FAIL: $FAIL  WARN: $WARN"
if [ "$FAIL" -gt 0 ]; then
  echo "  *** FAILURES DETECTED ***"
  exit 1
else
  echo "  All checks passed."
fi
