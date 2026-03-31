#!/bin/bash
# Check build artifacts for external URL dependencies.
# Run after `npm run build` in frontend/ to verify air-gap readiness.

set -e

BUILD_DIR="${1:-frontend/.next}"
EXTERNAL_PATTERNS=(
  "unpkg.com"
  "cdn.jsdelivr.net"
  "cdnjs.cloudflare.com"
  "fonts.googleapis.com"
  "fonts.gstatic.com"
  "apis.google.com"
  "api.openai.com"
)

echo "=== onTong Air-Gap Dependency Check ==="
echo "Scanning: $BUILD_DIR"
echo ""

FOUND=0

for pattern in "${EXTERNAL_PATTERNS[@]}"; do
  # Exclude node_modules (framework internals, not our app code)
  MATCHES=$(grep -rl "$pattern" "$BUILD_DIR" --include='*.js' --include='*.html' --include='*.css' 2>/dev/null | grep -v 'node_modules' || true)
  if [ -n "$MATCHES" ]; then
    echo "FAIL: Found external URL '$pattern' in:"
    echo "$MATCHES" | while read -r f; do echo "  - $f"; done
    FOUND=$((FOUND + 1))
  fi
done

echo ""
if [ "$FOUND" -eq 0 ]; then
  echo "PASS: No external URLs found in build artifacts."
  exit 0
else
  echo "FAIL: $FOUND external URL pattern(s) found. Fix before air-gap deployment."
  exit 1
fi
