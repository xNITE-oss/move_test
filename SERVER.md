# Serverga ko'chirish — bosqichma-bosqich

Bot doim ishlab turadigan bo'ladi: tugma bosilsa **bir soniyada** javob beradi,
jadval aniq vaqtida ishlaydi. Umumiy vaqt: ~20 daqiqa. Narxi ~€5.5/oy.

Nima uchun kerak: GitHub Actions har safar noldan konteyner ko'taradi va jadvalni
kafolatlamaydi — `*/5` deb yozilsa ham 20–40 daqiqa kechikishi mumkin. Jadval
bo'yicha post uchun bu muammo emas, lekin tugma va buyruqlar uchun yaramaydi.

---

## 1-qadam. Server yaratish (5 daqiqa)

1. **https://www.hetzner.com/cloud** → **Sign up**, hisob oching
   (karta yoki PayPal bilan tasdiqlash so'raladi)
2. Konsolda **New project** → nomi: `movespace`
3. **Add server** tugmasi. Sozlamalar:

   | Maydon | Tanlang |
   |---|---|
   | Location | **Falkenstein** yoki **Helsinki** (arzonroq) |
   | Image | **Ubuntu 24.04** |
   | Type | **Shared vCPU → CX23** (2 vCPU, 4 GB) |
   | Networking | IPv4 yoqilgan holda qoldiring |
   | SSH Keys | Hozircha o'tkazib yuboring |
   | Name | `movespace` |

4. **Create & Buy now**

Bir daqiqada server tayyor bo'ladi. Sizga **IP manzil** (masalan `95.217.x.x`)
va elektron pochtaga **root paroli** keladi.

---

## 2-qadam. Serverga ulanish

Mac'da **Terminal** oching va yozing (IP o'rniga o'zingiznikini):

```bash
ssh root@95.217.0.0
```

- "Are you sure you want to continue connecting?" → `yes`
- Parol so'raydi → pochtadagi parolni **qo'ying** (yozganingiz ko'rinmaydi, bu normal)
- Birinchi kirishda yangi parol o'ylab topishni so'raydi — eski parolni yana bir
  marta, keyin yangisini ikki marta kiritasiz. Yangi parolni saqlab qo'ying

Muvaffaqiyatli bo'lsa `root@movespace:~#` ko'rinadi.

---

## 3-qadam. O'rnatish (bitta buyruq)

Server ichida turib:

```bash
apt update -qq && apt install -y -qq git
git clone --depth 1 https://github.com/xNITE-oss/move_test.git /tmp/ms
bash /tmp/ms/deploy/install.sh https://github.com/xNITE-oss/move_test.git
```

Skript o'zi hamma narsani qiladi va oxirida **kalitlarni so'raydi**:

```
Gemini kaliti (AQ....):
Tavily kaliti (tvly-...):
Telegram bot tokeni:
Kanal ID (masalan -1004330535265):
Sizning Telegram ID'ingiz:
```

Har birini qo'yib Enter bosing. Oxirida shunday ko'rinishi kerak:

```
  ✅ bot ishlayapti
  ✅ scheduler ishlayapti
```

---

## 4-qadam. Tekshirish

Telegram'da botga **📝 Post tayyorlash** deb bosing.

Endi javob **darhol** keladi — 5 daqiqa kutish yo'q. Rubrika tanlaysiz, post
bir-ikki daqiqada tayyorlanib, tasdiqqa keladi. ✅ bosasiz — kanalga **shu zahoti**
chiqadi.

---

## 5-qadam. GitHub workflow'larini o'chiring ← muhim

Aks holda ikkita tizim bir vaqtda ishlaydi: postlar takrorlanadi va tugma
bosilishini qaysi biri birinchi o'qisa, o'sha oladi.

GitHub → **Actions** → chapdagi har bir workflow'ni tanlab, o'ng yuqoridagi
**"..."** → **Disable workflow**. Uchalasini ham:

- Move Space — post tayyorlash
- Move Space — tasdiqni tekshirish
- Move Space — tekshirish

Kod GitHub'da qolaveradi — server undan yangilanadi.

---

## Kundalik ishlar

**Kodni yangilash** (men yangi versiya berganimda):

```bash
ssh root@SIZNING-IP
bash /opt/movespace/app/deploy/update.sh
```

Skript kodni tortadi, testlarni yurgizadi va **testlar o'tsagina** xizmatlarni
qayta ishga tushiradi.

**Jonli logni ko'rish:**

```bash
journalctl -u movespace-bot -f          # bot: tugmalar, buyruqlar
journalctl -u movespace-scheduler -f    # jadval bo'yicha postlar
```

Chiqish uchun `Ctrl+C`.

**Holat:**

```bash
systemctl status movespace-bot
```

**Qayta ishga tushirish:**

```bash
systemctl restart movespace-bot movespace-scheduler
```

**Kalitni almashtirish:**

```bash
nano /opt/movespace/app/.env      # tahrirlab, Ctrl+O → Enter → Ctrl+X
systemctl restart movespace-bot movespace-scheduler
```

---

## Bilib qo'ying

- **Baza endi serverda** (`/opt/movespace/app/data/state.db`) — GitHub'ga commit
  qilinmaydi, ya'ni `git pull` ziddiyatlari ham tugaydi
- **Xizmatlar o'zi tiklanadi**: xato bo'lsa yoki server qayta yuklansa,
  systemd ularni avtomatik qayta ishga tushiradi
- **Zaxira nusxa**: Hetzner konsolida **Backups** yoqsangiz (narxning 20%),
  har kuni avtomatik snapshot olinadi. Yoki vaqti-vaqti bilan
  `scp root@IP:/opt/movespace/app/data/state.db ~/` qilib tortib qo'ying
- **Keyinchalik**: adminka va sayt ham shu serverda turadi. 4 GB RAM Postgres,
  backend va botni birga ko'taradi
