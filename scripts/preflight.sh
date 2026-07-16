#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Preflight: Aperture"

command -v docker >/dev/null || { echo "docker required"; exit 1; }
command -v python3 >/dev/null || { echo "python3 required"; exit 1; }

echo "==> Train ML models (if missing)"
if [ ! -f data/models/manifest.json ]; then
  python3 scripts/train_models.py
fi

echo "==> Backend unit tests"
cd backend
python3 -m pip install -q -r requirements.txt pytest 2>/dev/null || pip install -q -r requirements.txt pytest
PYTHONPATH=. python3 -m pytest tests/ -q
cd "$ROOT"

echo "==> Docker compose build"
docker compose build --quiet

echo "==> Docker compose up"
docker compose up -d
sleep 5

echo "==> Health check"
curl -sf http://127.0.0.1:8000/health | grep -q ok
curl -sf http://127.0.0.1:5173/ | grep -q html

echo "==> Import + replay smoke"
curl -sf -X POST http://127.0.0.1:8000/api/import
curl -sf -X POST "http://127.0.0.1:8000/api/replay/start?speed=10"
sleep 8
curl -sf http://127.0.0.1:8000/api/incidents | grep -q incident_id

echo ""
echo "✅ Preflight passed"
echo "   Dashboard: http://127.0.0.1:5173"
echo "   API:       http://127.0.0.1:8000/docs"
