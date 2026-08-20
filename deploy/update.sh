#!/usr/bin/env bash
#
# Kodni GitHub'dan yangilaydi va xizmatlarni qayta ishga tushiradi.
#     bash /opt/movespace/app/deploy/update.sh
#
set -euo pipefail

APP_DIR=/opt/movespace/app
VENV=/opt/movespace/venv

[ "$(id -u)" -eq 0 ] || { echo "root sifatida ishga tushiring: sudo bash update.sh"; exit 1; }

# Kodni yangilaydi. `data/` papkasi (baza va arxiv) saqlanib qoladi —
# bot ishlab turgani uchun ish daraxti doim "iflos" bo'ladi, shuning uchun
# oddiy `git pull` o'rniga majburan remote holatiga tenglashtiramiz.
refresh_code() {
  local branch backup
  # Repo movespace egaligida, skript esa root'da ishlaydi — git "dubious
  # ownership" deb rad etmasligi uchun katalogni ishonchli deb belgilaymiz.
  git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true
  branch="$(git -C "$APP_DIR" rev-parse --abbrev-ref HEAD)"
  backup="$(mktemp -d)"
  [ -d "$APP_DIR/data" ] && cp -a "$APP_DIR/data/." "$backup/" 2>/dev/null || true
  git -C "$APP_DIR" fetch -q --depth 20 origin "$branch"
  git -C "$APP_DIR" reset -q --hard "origin/$branch"
  mkdir -p "$APP_DIR/data"
  cp -a "$backup/." "$APP_DIR/data/" 2>/dev/null || true
  rm -rf "$backup"
}

echo "==> Kod yangilanmoqda"
refresh_code

echo "==> Kutubxonalar"
"$VENV/bin/pip" install -q -r "$APP_DIR/requirements.txt"

echo "==> Testlar"
if ! (cd "$APP_DIR" && "$VENV/bin/python" -m pytest -q 2>&1 | tail -3); then
  echo "!  Testlar o'tmadi — xizmatlar qayta ishga tushirilmadi"
  exit 1
fi

chown -R movespace:movespace /opt/movespace

echo "==> Xizmatlar qayta ishga tushirilmoqda"
systemctl restart movespace-bot movespace-scheduler
sleep 2
systemctl is-active --quiet movespace-bot       && echo "  ✅ bot"       || echo "  ❌ bot"
systemctl is-active --quiet movespace-scheduler && echo "  ✅ scheduler" || echo "  ❌ scheduler"
