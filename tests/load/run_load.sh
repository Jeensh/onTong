#!/bin/bash
# Convenience runner: seed 1K docs, then run locust against localhost:8002 for 60s.
set -e

WORKTREE=$(git rev-parse --show-toplevel)
VENV_PYTHON="/Users/donghae/workspace/ai/onTong/.venv/bin/python"
BASE_URL="${BASE_URL:-http://localhost:8002}"
COUNT="${COUNT:-1000}"
DURATION="${DURATION:-60s}"
USERS="${USERS:-50}"

echo "=== Seeding $COUNT docs ==="
"$VENV_PYTHON" "$WORKTREE/tests/load/seed_1k.py" --count "$COUNT" --base-url "$BASE_URL"

echo ""
echo "=== Locust headless ==="
"$VENV_PYTHON" -m locust \
    -f "$WORKTREE/tests/load/locustfile.py" \
    --host "$BASE_URL" \
    --users "$USERS" --spawn-rate 5 \
    --run-time "$DURATION" \
    --headless

echo ""
echo "=== Done. Cleanup with: ==="
echo "    Optionally remove load_test_demo/ folder via:"
echo "    curl -X PATCH \$BASE_URL/api/wiki/folder/load_test_demo -d '{\"new_path\":\"_archive_load_test\"}' -H 'X-User-Id: donghae' -H 'Content-Type: application/json'"
