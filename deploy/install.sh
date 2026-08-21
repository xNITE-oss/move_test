#!/usr/bin/env bash
#
# Move Space kontent-botini serverga o'rnatadi (Ubuntu 22.04 / 24.04).
# Qayta ishga tushirish xavfsiz — mavjud sozlamalarni buzmaydi.
#
# Ishlatish (server ichida, root sifatida):
#     bash install.sh https://github.com/FOYDALANUVCHI/REPO.git
#
set -euo pipefail

REPO_URL="${1:-}"
APP_ROOT=/opt/movespace
APP_DIR="$APP_ROOT/app"
VENV="$APP_ROOT/venv"
SERVICE_USER=movespace

say()  { printf "\n\033[1;32m==> %s\033[0m\n" "$1"; }
warn() { printf "\033[1;33m!  %s\033[0m\n" "$1"; }
die()  { printf "\033[1;31m✗  %s\033[0m\n" "$1" >&2; exit 1; }

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

[ "$(id -u)" -eq 0 ] || die "root sifatida ishga tushiring: sudo bash install.sh <repo-url>"

if [ -z "$REPO_URL" ] && [ ! -d "$APP_DIR/.git" ]; then
  die "Repozitoriy havolasini bering: bash install.sh https://github.com/.../repo.git"
fi

# ── 1. Kerakli paketlar ─────────────────────────────────────────────────────
say "Paketlar o'rnatilmoqda"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git tzdata >/dev/null
timedatectl set-timezone Asia/Tashkent 2>/dev/null || warn "Vaqt zonasi o'rnatilmadi"

# ── 2. Xizmat foydalanuvchisi ───────────────────────────────────────────────
if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
  say "'$SERVICE_USER' foydalanuvchisi yaratilmoqda"
  useradd --system --create-home --home-dir "$APP_ROOT" --shell /usr/sbin/nologin "$SERVICE_USER"
fi
mkdir -p "$APP_ROOT"

# ── 3. Kod ──────────────────────────────────────────────────────────────────
if [ -d "$APP_DIR/.git" ]; then
  say "Kod yangilanmoqda"
  refresh_code
else
  say "Kod yuklab olinmoqda"
  git clone --depth 20 "$REPO_URL" "$APP_DIR"
fi

# ── 4. Python muhiti ────────────────────────────────────────────────────────
say "Python kutubxonalari"
[ -d "$VENV" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r "$APP_DIR/requirements.txt"

# ── 5. Kalitlar ─────────────────────────────────────────────────────────────
ENV_FILE="$APP_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  say "Kalitlarni kiriting (Enter bosib o'tkazib yuborsangiz keyin qo'shasiz)"
  ask() {
    local var="$1" prompt="$2" value
    read -rp "$prompt: " value </dev/tty
    [ -n "$value" ] && printf '%s=%s\n' "$var" "$value" >> "$ENV_FILE"
  }
  # Adminka token imzosi uchun maxfiy kalit — avtomatik yaratiladi
  jwt_secret="$(openssl rand -base64 48 2>/dev/null | tr -d '\n' || head -c 48 /dev/urandom | base64 | tr -d '\n')"
  {
    echo "# Move Space — server sozlamalari"
    echo "LLM_PROVIDER=gemini"
    echo "GEMINI_TEXT_MODEL=gemini-3.5-flash"
    echo "GEMINI_FALLBACK_MODELS=gemini-3.5-flash-lite,gemini-flash-lite-latest"
    echo "SEARCH_PROVIDER=tavily"
    echo "IMAGE_PROVIDER=none"
    echo "TTS_PROVIDER=none"
    echo "TIMEZONE=Asia/Tashkent"
    echo "LOG_LEVEL=INFO"
    echo "# --- Adminka (web) ---"
    echo "ADMIN_USERNAME=admin"
    echo "JWT_SECRET=$jwt_secret"
  } > "$ENV_FILE"
  ask GEMINI_API_KEY          "Gemini kaliti (AQ....)"
  ask TAVILY_API_KEY          "Tavily kaliti (tvly-...)"
  ask TELEGRAM_BOT_TOKEN      "Telegram bot tokeni"
  ask TELEGRAM_CHANNEL_ID     "Kanal ID (masalan -1004330535265)"
  ask TELEGRAM_REVIEW_CHAT_ID "Sizning Telegram ID'ingiz"
  ask ADMIN_PASSWORD          "Adminka paroli (o'zingiz o'ylab toping)"
else
  say "Mavjud .env topildi — tegilmadi"
fi
chmod 600 "$ENV_FILE"
chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_ROOT"

# ── 6. Xizmatlar ────────────────────────────────────────────────────────────
say "Systemd xizmatlari o'rnatilmoqda"
install -m 644 "$APP_DIR/deploy/movespace-bot.service"       /etc/systemd/system/
install -m 644 "$APP_DIR/deploy/movespace-scheduler.service" /etc/systemd/system/
install -m 644 "$APP_DIR/deploy/movespace-web.service"       /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now movespace-bot.service movespace-scheduler.service movespace-web.service

sleep 2
say "Holat"
systemctl is-active --quiet movespace-bot       && echo "  ✅ bot ishlayapti"       || echo "  ❌ bot ishlamadi"
systemctl is-active --quiet movespace-scheduler && echo "  ✅ scheduler ishlayapti" || echo "  ❌ scheduler ishlamadi"
systemctl is-active --quiet movespace-web       && echo "  ✅ web API ishlayapti"   || echo "  ❌ web API ishlamadi"

cat <<'EOF'

────────────────────────────────────────────────────────────
Tayyor. Foydali buyruqlar:

  systemctl status movespace-bot        # holat
  journalctl -u movespace-bot -f        # jonli log
  journalctl -u movespace-scheduler -f  # jadval logi
  bash /opt/movespace/app/deploy/update.sh   # yangilash

MUHIM: endi GitHub'dagi workflow'larni o'chiring, aks holda
ikkita tizim bir vaqtda ishlab, postlar takrorlanadi.
GitHub → Actions → har bir workflow → "..." → Disable workflow
────────────────────────────────────────────────────────────
EOF
