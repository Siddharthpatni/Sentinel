#!/usr/bin/env bash
# One-command Sentinel demo: boot the stack, wait for health, seed varied
# traces, and open the dashboard. Idempotent — safe to re-run.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  cat >&2 <<EOF
ERROR: OPENAI_API_KEY is not set.

The seed step makes a handful of cheap (gpt-4o-mini, <\$0.01) calls so the
dashboard has data to show. Export your key and re-run:

    export OPENAI_API_KEY=sk-...
    ./scripts/demo.sh
EOF
  exit 2
fi

echo "▶ booting docker compose stack..."
docker compose up -d

echo "▶ waiting for gateway to become healthy..."
for i in $(seq 1 30); do
  if curl -fs http://localhost:8000/health >/dev/null 2>&1; then
    echo "  gateway up"
    break
  fi
  sleep 1
done
if ! curl -fs http://localhost:8000/health >/dev/null 2>&1; then
  echo "✗ gateway did not become healthy in 30s. Check: docker compose logs gateway" >&2
  exit 1
fi

echo "▶ installing SDK (editable)..."
pip install -e ./sdk --quiet

echo "▶ seeding demo data..."
python examples/seed_demo.py

URL="http://localhost:3000"
echo ""
echo "✓ Sentinel is live at $URL"

# Open browser if we can (macOS/Linux/WSL)
if command -v open >/dev/null 2>&1; then
  open "$URL"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" >/dev/null 2>&1 || true
fi
