#!/usr/bin/env bash
#
# Saytni (web/) build qilib serverga yuklaydi.
# Mahalliy kompyuterda ishga tushiring (server emas):
#     bash deploy/site-deploy.sh [ssh-host]
#
# ssh-host — standart: movespace (~/.ssh/config dagi alias).
set -euo pipefail

HOST="${1:-movespace}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB="$ROOT/web"
REMOTE_DIR="/var/www/movespace"

command -v npm >/dev/null || { echo "npm topilmadi"; exit 1; }

echo "==> Build (statik SPA)"
cd "$WEB"
npm install --no-audit --no-fund
NUXT_IGNORE_LOCK=1 npm run generate

echo "==> Serverga yuklash ($HOST:$REMOTE_DIR)"
ssh "$HOST" "mkdir -p $REMOTE_DIR"
rsync -az --delete "$WEB/.output/public/" "$HOST:$REMOTE_DIR/"
ssh "$HOST" "chown -R caddy:caddy $REMOTE_DIR 2>/dev/null || chmod -R a+rX $REMOTE_DIR; systemctl reload caddy"

echo "==> Tayyor: https://movespace.uz"
