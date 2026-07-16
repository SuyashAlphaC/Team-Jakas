#!/usr/bin/env bash
# Deploy Vite dashboard to Vercel (requires backend URL).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FRONTEND="${ROOT}/frontend"
BACKEND_URL_FILE="${ROOT}/deploy/aws/.backend-url"

if [[ -f "${BACKEND_URL_FILE}" ]]; then
  BACKEND_HOST="$(tr -d '[:space:]' < "${BACKEND_URL_FILE}")"
else
  BACKEND_HOST="${VITE_API_URL:-}"
fi

if [[ -z "${BACKEND_HOST}" ]]; then
  echo "Set VITE_API_URL or run deploy/aws/deploy.sh first"
  exit 1
fi

# Ensure https, no trailing slash
BACKEND_HOST="${BACKEND_HOST#https://}"
BACKEND_HOST="${BACKEND_HOST#http://}"
BACKEND_HOST="${BACKEND_HOST%/}"
API_URL="https://${BACKEND_HOST}"

echo "==> Backend API: ${API_URL}"

cd "${FRONTEND}"

if ! vercel whoami >/dev/null 2>&1; then
  echo "Run: vercel login"
  exit 1
fi

# Link project non-interactively if not linked
if [[ ! -f .vercel/project.json ]]; then
  vercel link --yes --project context-aware-observability 2>/dev/null \
    || vercel link --yes
fi

echo "==> Set VITE_API_URL for production"
vercel env rm VITE_API_URL production -y 2>/dev/null || true
printf '%s' "${API_URL}" | vercel env add VITE_API_URL production

echo "==> Deploy to Vercel production"
cd "${FRONTEND}"
vercel deploy --prod --yes

echo ""
echo "Backend URL:  ${API_URL}"
