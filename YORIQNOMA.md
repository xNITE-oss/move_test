# Ishga tushirish yo'riqnomasi — bosqichma-bosqich

Bu yo'riqnoma texnik bilim talab qilmaydi. Har bir qadamda nima bosishingiz
va nima ko'rishingiz yozilgan. Umumiy vaqt: ~20 daqiqa.

Hozirgi holat:

| Narsa | Holat |
|---|---|
| Telegram bot `@move_test_content_bot` | ✅ ishlaydi |
| Kanal "Move Space \| Uzbekistan" | ✅ bot admin, post yubora oladi |
| Tavily (material qidirish) | ✅ ishlaydi |
| LLM (post yozuvchi) | ❌ hali yo'q — 1-qadam shu haqda |

---

## 1-qadam. Bepul Gemini kaliti olish (5 daqiqa)

Anthropic kalitida balans yo'q, shuning uchun bepul variantdan boshlaymiz.
Google Gemini'ning bepul tarifi bu vazifa uchun yetarli.

1. Brauzerda oching: **https://aistudio.google.com/apikey**
2. Google akkauntingiz bilan kiring
3. **"Create API key"** tugmasini bosing
4. Loyiha so'rasa — **"Create API key in new project"** ni tanlang
5. Chiqqan kalitni **nusxa oling**

> ⚠️ **Kalit `AIza` bilan boshlanishi kerak** (masalan `AIzaSyB...`).
> Agar sizdagi kalit boshqacha ko'rinishda bo'lsa — bu API kaliti emas, balki
> boshqa token. U holda yuqoridagi sahifaga qaytib, **"Create API key"**
> tugmasidan olingan kalitni oling.

Kalitni hozircha bloknotga saqlab turing — 4-qadamda kerak bo'ladi.

> **Eslatma:** bepul tarifda kunlik so'rovlar soni cheklangan, lekin bizga kuniga
> 1-2 ta post kerak — bu chegaraga hatto yaqinlashmaydi ham.

---

## 2-qadam. GitHub'da hisob va repozitoriy ochish (5 daqiqa)

Repozitoriy — bu kodingiz turadigan papka. Bot o'sha yerdan ishlaydi.

1. **https://github.com** ga kiring (hisobingiz bo'lmasa — **Sign up**)
2. O'ng yuqoridagi **"+"** belgisini bosing → **"New repository"**
3. **Repository name** maydoniga yozing: `movespace-bot`
4. **Public** ni tanlang (siz shuni tanladingiz)
   - Kod hammaga ko'rinadi, lekin **kalitlar ko'rinmaydi** — ular kodda emas,
     GitHub'ning shifrlangan Secrets seyfida saqlanadi
   - Public repoda GitHub Actions bepul va cheksiz ishlaydi
   - ⚠️ Kalitni hech qachon fayl ichiga yozmang. Faqat Secrets orqali (4-qadam)
5. Pastdagi **"Create repository"** tugmasini bosing

Bo'sh repozitoriy ochiladi. Hozircha shu yetadi.

---

## 3-qadam. Fayllarni yuklash (10 daqiqa)

Ikki qismdan iborat. **Ikkinchisini o'tkazib yubormang** — usiz avtomatika ishlamaydi.

### 3A. Oddiy fayllarni yuklash

1. Yuborgan `movespace_bot.zip` faylini kompyuteringizda **oching (unzip)**
2. GitHub'da repozitoriy sahifasida **"uploading an existing file"** havolasini bosing
   (bo'sh repo sahifasining o'rtasida turadi)
3. Ochilgan oynaga `movespace_bot` papkasi **ichidagi hamma narsani** sudrab tashlang:
   `agents`, `config`, `core`, `prompts`, `providers`, `scheduler`, `tests`,
   `cli.py`, `requirements.txt`, `README.md` va qolganlari
4. Pastda **"Commit changes"** tugmasini bosing

### 3B. Ikkita workflow faylini joyiga qo'yish

`.github` papkasi nuqta bilan boshlangani uchun kompyuteringizda **yashirin** —
sudrab olishda ko'rinmaydi. Yuklaganingizdan keyin repozitoriyda `.github`
papkasi bor-yo'qligini tekshiring.

**Agar `.github` papkasi ko'rinsa** — hammasi joyida, 4-qadamga o'ting.

**Agar ko'rinmasa** — quyidagini qiling. Bu eng oson yo'l, hech narsa
ko'chirib yozish (copy-paste) shart emas:

1. Men alohida yuborgan **`post.yml`** va **`approve.yml`** fayllarini yuklab oling
2. Repozitoriyda **"Add file"** → **"Upload files"** → ikkalasini sudrab tashlang →
   **"Commit changes"**. Ular repozitoriy ildizida paydo bo'ladi
3. Endi ularni joyiga ko'chiramiz. **`post.yml`** faylining ustiga bosing →
   o'ng yuqoridagi **qalam** (✏️ Edit) belgisini bosing
4. Yuqoridagi **fayl nomi** maydonida `post.yml` yozuvi turadi. Uni o'chirib,
   o'rniga **aynan shuni** yozing:
   ```
   .github/workflows/post.yml
   ```
   `/` yozganingizda GitHub o'zi papka yasaydi — shunday bo'lishi kerak
5. **"Commit changes"** → yana **"Commit changes"**
6. Xuddi shu ishni **`approve.yml`** bilan takrorlang, nomi:
   `.github/workflows/approve.yml`

Tekshirish: repozitoriyda `.github` papkasi bo'lishi kerak, ichida `workflows`,
undan ichkarida ikkita `.yml` fayl. Ildizda esa yolg'iz `post.yml` qolmasin —
nomini o'zgartirsangiz, GitHub uni ko'chiradi, nusxa qoldirmaydi.

---

### 3V. Muqobil: terminal orqali (parol emas, token kerak)

GitHub 2021 yildan beri **parolni qabul qilmaydi**. Terminal parol so'raganda
akkaunt parolingizni emas, **token** (Personal Access Token) kiritasiz.

**Token olish:**

1. github.com → o'ng yuqorida rasmingiz → **Settings**
2. Chap ustunning eng pastida → **Developer settings**
3. **Personal access tokens** → **Tokens (classic)** → **Generate new token (classic)**
4. **Note**: `movespace` deb yozing, **Expiration**: 90 days
5. Belgilanadigan ruxsatlar — **ikkalasi ham kerak**:
   - ✅ **repo** (barcha ostidagilar bilan)
   - ✅ **workflow** ← bunsiz `.github/workflows` fayllari yuklanmaydi
6. Pastda **Generate token** → chiqqan `ghp_...` matnini **nusxa oling**
   (sahifani yopsangiz qayta ko'rsatilmaydi)

**Terminal buyruqlari** (zip ochilgan papka ichida turib):

```bash
cd movespace_bot            # zip ochilgan papka
git init
git add -A
git commit -m "Move Space kontent-boti"
git branch -M main
git remote add origin https://github.com/xNITE-oss/move_test.git
git push -u origin main --force
```

`Username` so'raganda: `xNITE-oss`
`Password` so'raganda: **tokenni qo'ying** (`ghp_...`). Terminal yozganingizni
ko'rsatmaydi — bu normal, qo'yib Enter bosing.

> `--force` kerak, chunki repozitoriyda allaqachon zip fayli turgan bo'lishi mumkin —
> bu buyruq uni almashtiradi.

Token ishini bajargach uni o'chirib qo'ysangiz bo'ladi:
Settings → Developer settings → Tokens → **Delete**.

---

## 4-qadam. Kalitlarni Secrets'ga qo'shish (5 daqiqa)

**Secrets** — bu GitHub'ning shifrlangan seyfi. Kalitlar shu yerda saqlanadi:
kodda ko'rinmaydi, loglarga chiqmaydi, boshqa odamlar o'qiy olmaydi.

Yo'l: repozitoriy sahifasi → yuqoridagi **Settings** (⚙️) →
chap ustunda **Secrets and variables** → ostidagi **Actions**

Ochilgan sahifada yashil **"New repository secret"** tugmasi bor. Har bir kalit uchun:
tugmani bosasiz → **Name** va **Secret** maydonlarini to'ldirasiz → **Add secret**.

Beshta kalit qo'shasiz (nomlarni **aynan shunday** yozing, katta harflar bilan):

| # | Name (nomi) | Secret (qiymati) |
|---|---|---|
| 1 | `GEMINI_API_KEY` | 1-qadamda olgan kalitingiz (`AIza...`) |
| 2 | `TAVILY_API_KEY` | `tvly-dev-...` bilan boshlanadigan kalitingiz |
| 3 | `TELEGRAM_BOT_TOKEN` | BotFather bergan token (`8955...:AAE...`) |
| 4 | `TELEGRAM_CHANNEL_ID` | `-1004330535265` |
| 5 | `TELEGRAM_REVIEW_CHAT_ID` | `6121632867` |

Hammasi qo'shilgach ro'yxatda 5 ta qator turadi. Qiymatlarni ko'ra olmaysiz —
bu normal, GitHub ularni hech kimga ko'rsatmaydi.

> **Nega `-1004330535265`, `@movespace` emas?** Kanalingiz yopiq, shuning uchun
> raqamli ID ishonchliroq. Men uni tekshirdim — bot aynan shu kanalda admin.

---

## 5-qadam. Botga yozish ruxsatini berish (1 daqiqa)

Bot o'zi chiqargan mavzularni eslab qolishi kerak — shunda bir xil post ikki marta
chiqmaydi. Buning uchun unga repozitoriyga yozish ruxsati kerak.

1. **Settings** → chap ustunda **Actions** → **General**
2. Sahifani pastga aylantiring → **"Workflow permissions"** bo'limini toping
3. **"Read and write permissions"** ni belgilang
4. **Save** tugmasini bosing

---

## 6-qadam. Birinchi postni sinash (2 daqiqa)

1. Yuqoridagi **Actions** bo'limiga o'ting
2. Agar "Workflows aren't being run on this forked repository" yoki shunga o'xshash
   ogohlantirish chiqsa — **"I understand my workflows, go ahead and enable them"** ni bosing
3. Chap ustundan **"Move Space — post tayyorlash"** ni tanlang
4. O'ng tomonda **"Run workflow"** tugmasi chiqadi, uni bosing
5. **rubric** ro'yxatidan `running` ni tanlang → yana **"Run workflow"**

Sariq doira aylanadi (ishlayapti) → ~1-2 daqiqada yashil ✓ bo'ladi.

Shundan keyin **Telegram'da botdan xabar keladi** — tayyor post va uchta tugma:

- ✅ **Chiqarish** — post kanalga chiqadi
- ✏️ **Qayta yozish** — boshqa variant tayyorlanadi
- ❌ **Bekor** — chiqmaydi

> ✅ bosgandan keyin post 15 daqiqagacha kutishi mumkin — tasdiqni tekshiruvchi
> workflow har 15 daqiqada ishlaydi. Bu normal.

Agar qizil ✗ chiqsa: ishning ustiga bosing → qaysi qadam qizil bo'lganini oching →
xato matnini menga yuboring, birga tuzatamiz.

---

## 7-qadam. Keyin nima bo'ladi

Hech narsa qilmasangiz ham bot jadval bo'yicha ishlaydi:

| Kun | Vaqt | Rubrika |
|---|---|---|
| Dushanba, Payshanba | 07:00 | 🏃 Running |
| Seshanba | 19:00 | 🚴 Cycling |
| Seshanba, Juma | 12:00 | 🇺🇿 Move UZ |
| Chorshanba | 19:00 | 🏅 Race |
| Juma | 18:00 | ⛰️ Hiking |
| Shanba | 10:00 | 🏕️ Camping |
| Yakshanba | 11:00 | 👟 Active Life |

Har safar post avval **sizga** keladi, siz ✅ bosmaguningizcha kanalga chiqmaydi.

Bir-ikki hafta shunday yurib, sifat barqaror bo'lganini ko'rsangiz — ba'zi
rubrikalarni to'liq avtomatga o'tkazamiz (`move_uz` dan tashqari: unda sana va
joy bo'ladi, ularni odam ko'rgani ma'qul).

---

## Eng muhim narsa: uslub

`config/style/samples.md` faylida hozir men yozgan namunalar turibdi. Writer
aynan shulardan ohang oladi. O'zingizning 3-5 ta real postingizni qo'ysangiz,
postlar sizning uslubingizga o'xshab qoladi. Bu sifatga eng ko'p ta'sir qiladigan
bitta narsa.

---

## Xavfsizlik eslatmasi

Kalitlaringiz suhbatda ochiq yozilgani uchun, hammasi ishlab ketgach almashtiring:

- Telegram: @BotFather → `/revoke` → yangi token
- Tavily: dashboard → yangi kalit
- Anthropic: console → API Keys → eskisini o'chiring

Yangi kalitlarni GitHub Secrets'da yangilaysiz (Secrets → kalit yonidagi
**Update** tugmasi).
