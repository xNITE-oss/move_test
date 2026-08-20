# Move Space — Telegram kontent avtomatizatsiyasi

Rubrika berasiz → tizim internetdan material topadi, sizning uslubingizda post yozadi,
sifatini tekshiradi va Telegram'ga chiqaradi.

**Hozirgi holat:** Research + Writer + Quality + Publisher + tasdiq boti ishlaydi.
Image va Audio agentlari skeleton holatida — kalit qo'shib, config'da `enabled: true`
qilsangiz ishga tushadi, kod o'zgartirish shart emas.

**Deploy:** GitHub Actions (bepul) yoki VPS — 9-bo'limga qarang.
Claude Cowork sandbox'ida Telegram va Tavily API'lariga chiqish yopiq,
shuning uchun post o'sha yerdan chiqmaydi.

---

## 1. Tez boshlash

```bash
cd movespace_bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # kalitlarni to'ldiring

python cli.py doctor                              # sozlamalarni tekshirish
python cli.py run -r running --dry-run  # kalitsiz sinov
python cli.py run -r running            # haqiqiy ishga tushirish
```

`--dry-run` rejimida tarmoqqa umuman chiqilmaydi (fake providerlar ishlaydi) va
Telegram'ga hech narsa yuborilmaydi — tuzilmani sinash uchun.

### CLI buyruqlari

| Buyruq | Vazifasi |
|---|---|
| `python cli.py rubrics` | Rubrikalar ro'yxati va jadvali |
| `python cli.py run -r <kalit>` | Bitta rubrika bo'yicha post |
| `python cli.py run -r <kalit> -t "mavzu"` | Mavzuni qo'lda berish |
| `python cli.py run-all` | Barcha yoqilgan rubrikalar |
| `python cli.py history` | Chiqqan postlar tarixi |
| `python cli.py schedule` | Cron bo'yicha doimiy ishlash |
| `python cli.py doctor` | Qaysi kalit yetishmayotganini ko'rsatadi |

---

## 2. Arxitektura

```
Rubric YAML ──► Pipeline ──► Research ──► Writer ──► Image ──► Audio ──► Quality ──► Publisher
                   │                        ▲                              │
                   │                        └────── feedback (retry) ──────┘
                   ▼
              Storage (data/runs/... + SQLite)
```

Uchta qoida butun tizimni ushlab turadi:

1. **Bitta kontekst.** Barcha agentlar `PostContext` obyektini o'qiydi va boyitib qaytaradi.
   Agentlar bir-birini bilmaydi.
2. **Agentlar API bilan gaplashmaydi.** Har qanday tashqi xizmat `providers/` qatlamida.
   ElevenLabs o'rniga boshqa TTS qo'ysangiz — faqat `providers/tts.py` o'zgaradi.
3. **Xulq config'da, kodda emas.** Qaysi agent ishlashi, uslub, jadval — hammasi
   rubrika YAML'ida.

### Bitta post — ko'p kanal

Writer tayyor Telegram matnini emas, **tuzilgan kontent** qaytaradi:

```
PostContent(title, lead, body[], takeaway, cta, tags)
        │
        ├──► render_telegram()  → emoji, 900 belgi, hashtag
        ├──► render_markdown()  → sayt uchun front-matter'li fayl
        └──► render_html()      → adminka ko'rinishi
```

Shu sababli saytga chiqarish qo'shilganda Writer ham, promptlar ham, uslub
namunalari ham qayta yozilmaydi — faqat yangi renderer qo'shiladi.

Post qayerga chiqishi rubrikada belgilanadi:

```yaml
publish_to: [telegram]          # sayt qo'shilganda: [telegram, web]
```

`web` yoqilganda `data/site/<rubrika>/<sana>-<slug>.md` fayli yoziladi —
statik generator yoki backend shuni o'qiydi. Yangi kanal qo'shish uchun
`agents/publisher_agent.py` ga `_target_<nom>` metodini yozish kifoya.

### Xizmat qatlami

Biznes-mantiq `core/service.py` da — `ContentService`. Telegram boti ham,
keyingi web-adminka ham aynan shu metodlarni chaqiradi:

```python
service.create_post("running")      # to'liq pipeline
service.list_posts(limit=20)        # tarix
service.get_content(run_id)         # tuzilgan kontent (sayt uchun)
await service.publish(post)         # tasdiqlangandan keyin
service.reject(run_id)
```

Adminka yozilganda mantiq qayta yozilmaydi — ustiga yupqa HTTP qobiq kiyiladi.

### Papkalar

| Papka | Nima uchun |
|---|---|
| `core/` | Pipeline, kontent modeli, renderer'lar, xizmat qatlami, storage |
| `agents/` | Har bir agent — alohida fayl |
| `providers/` | Tashqi API'lar (LLM, search, image, TTS, Telegram) |
| `prompts/` | Prompt shablonlari — kodga tegmasdan tahrirlanadi |
| `config/rubrics/` | Har rubrika — alohida YAML |
| `config/style/` | Uslub namunalari (sizning real postlaringiz) |
| `data/` | Natijalar arxivi + SQLite holat bazasi |

---

## 3. Kanal rubrikalari

| Kalit | Rubrika | Jadval (Toshkent) | Post turi |
|---|---|---|---|
| `running` | 🏃 Running | Dush, Pay 07:00 | Mashg'ulot va texnika maslahatlari |
| `race` | 🏅 Race | Chor 19:00 | Zabeg tayyorgarligi va strategiya |
| `hiking` | ⛰️ Hiking | Jum 18:00 | Marshrut, jihoz, xavfsizlik |
| `camping` | 🏕️ Camping | Shan 10:00 | Chodir, tunash, outdoor asoslari |
| `cycling` | 🚴 Cycling | Sesh 19:00 | Velosiped: qatnov, sozlash, xavfsizlik |
| `active_life` | 👟 Active Life | Yak 11:00 | Tiklanish, odat, jihoz tanlash |
| `move_uz` | 🇺🇿 Move UZ | Sesh, Jum 12:00 | Mahalliy tadbir, community, sportchilar |

Jadval ataylab bir-birining ustiga tushmaydi — haftasiga 9 ta post, kuniga 1 tadan.
Rubrikani vaqtincha to'xtatish: YAML'da `enabled: false`.

> **Move UZ haqida:** bu rubrika sana, joy va narx bilan ishlaydi — ular tez eskiradi.
> Shuning uchun unda `recency_days: 45`, `min_score: 8.0`, `regenerate_from: research`
> qo'yilgan va `mode: auto` tavsiya etilmaydi. Chiqarishdan oldin sana va joyni
> o'zingiz bir marta tekshiring.

### Media majburiyligi

Har bir rubrikada ikkita bayroq bor:

```yaml
image_required: false    # true — rasm chiqmasa post ham chiqmaydi
audio_required: false    # true — audio chiqmasa post ham chiqmaydi
```

- `false` (standart) — rasm/audio agenti xato bersa, pipeline davom etadi va post
  matn holida chiqadi.
- `true` — media majburiy; agent xato bersa pipeline to'xtaydi va post `failed`
  bo'ladi. Provider `none` bo'lsa ham xato beradi, ya'ni tasodifan mediasiz chiqmaydi.

Hozir hammasi `false`, chunki `IMAGE_PROVIDER=none` va `TTS_PROVIDER=none`.
Gemini/ElevenLabs kalitini qo'shgach: avval `agents.image.enabled: true`, ishlagani
tasdiqlangach `image_required: true`.

---

## 4. Yangi rubrika qo'shish

`config/rubrics/` ichiga yangi YAML qo'ying — boshqa hech narsa kerak emas:

```yaml
name: "🏊 Swimming"
description: "Basseyn va ochiq suvda suzish: texnika, nafas, xavfsizlik"
enabled: true
language: uz
pipeline: [research, writer, quality, publisher]
max_retries: 2

image_required: false
audio_required: false

agents:
  research:
    enabled: true
    queries: ["swimming technique beginner breathing", "open water safety basics"]
    max_results: 5
  writer:
    enabled: true
    post_type: "amaliy maslahat posti — 3 ta bajariladigan qadam"
    max_chars: 850
    tone: "murabbiy ohangi: aniq, sokin, ortiqcha ilhomlantirishsiz"
    address_form: "siz-lab murojaat"
    emoji: "kam — 2-3 ta"
    structure: ["hook", "sabab", "3 ta qadam", "eslatma", "savol"]
    cta: "o'quvchidan tajribasini so'rovchi savol"
    hashtags: ["#swimming", "#movespace"]
    style_file: "config/style/samples.md"
    avoid:
      - "nazoratsiz ochiq suvda suzishni normallashtirish"
  quality:
    enabled: true
    use_llm: true
    min_score: 7.0
    min_chars: 260
    banned_words: ["bugungi postimizda", "xulosa qilib aytganda"]
  publisher:
    enabled: true
    mode: "review"

schedule:
  cron: "0 17 * * thu"      # kun nomlari bilan yozing: mon, tue, ...
  timezone: "Asia/Tashkent"
```

Tekshirish: `python cli.py run -r swimming --dry-run`, so'ng `python -m pytest -q`
(`tests/test_rubric_configs.py` har bir YAML'ni tekshiradi va cron to'qnashuvini topadi).

### Uslub qanday boshqariladi

| Parametr | Nima qiladi |
|---|---|
| `post_type` | Post janri: maslahat, e'lon, tushuntirish, solishtiruv |
| `tone` | Ohang — erkin matn, LLM'ga to'g'ridan-to'g'ri uzatiladi |
| `structure` | Post skeleti (hook → sabab → qadamlar → CTA) |
| `emoji` | Emoji miqdori |
| `avoid` | Shu rubrikada taqiqlangan mavzu/yondashuvlar |
| `banned_words` | Quality Agent matndan qidiradigan iboralar (qat'iy filtr) |

Sun'iy "AI uslubi"ga qarshi umumiy qoidalar `prompts/writer_post.md` ichida —
salomlashish marosimi, bo'sh motivatsiya, ortiqcha emoji, tarjima hidi taqiqlangan.
`avoid` va `banned_words` esa rubrikaga xos qo'shimcha filtr.

---

## 5. Yangi agent qo'shish

1. `agents/my_agent.py` — `BaseAgent` dan meros oling, `run(ctx)` ni yozing.
2. `core/registry.py` → `AGENT_REGISTRY` ga bitta qator qo'shing.
3. Rubrika YAML'da `pipeline` va `agents:` ga nom qo'shing.

```python
class MyAgent(BaseAgent):
    name = "my_agent"
    optional = True          # xato bo'lsa pipeline to'xtamaydi

    async def run(self, ctx: PostContext) -> PostContext:
        ctx.meta["salom"] = self.opt("param", "default")
        return ctx
```

---

## 6. Image / Audio agentlarini yoqish

**Rasm (Gemini):**
```env
IMAGE_PROVIDER=gemini
GEMINI_API_KEY=...
```
```yaml
agents:
  image:
    enabled: true
    style: "minimal editorial illustration, soft gradients"
```
> `providers/image.py` dagi endpoint va model nomini Google hujjatlari bilan
> solishtirib chiqing — bu qism sinovdan o'tkazilmagan.

**Audio (ElevenLabs):**
```env
TTS_PROVIDER=elevenlabs
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...
```
```yaml
agents:
  audio:
    enabled: true
```

---

## 7. Telegram sozlash

1. [@BotFather](https://t.me/BotFather) dan bot yarating → `TELEGRAM_BOT_TOKEN`.
2. Botni kanalingizga **admin** qiling (post yuborish huquqi bilan).
3. `TELEGRAM_CHANNEL_ID` — `@kanal_nomi` yoki `-100xxxxxxxxxx`.
4. `TELEGRAM_REVIEW_CHAT_ID` — o'z ID'ingiz ([@userinfobot](https://t.me/userinfobot)).

**Rejimlar** (`agents.publisher.mode`):

- `review` — post avval sizga tugmalar bilan keladi (standart, xavfsiz)
- `auto` — to'g'ridan-to'g'ri kanalga
- `off` — faqat saqlanadi

**Tasdiq tugmalari ishlashi uchun** `scheduler/approval_bot.py` ishlab turishi kerak:

```bash
python -m scheduler.approval_bot          # doimiy: ✅ bosilishi bilan chiqadi
python -m scheduler.approval_bot --once   # bir marta tekshiradi (cron/GitHub Actions)
```

Tugma bosilganda:

- ✅ **Chiqarish** — post kanalga chiqadi
- ✏️ **Qayta yozish** — shu rubrika bo'yicha yangi variant tayyorlanadi va sizga keladi
- ❌ **Bekor** — post `rejected` bo'ladi

Faqat `TELEGRAM_REVIEW_CHAT_ID` egasining bosishi qabul qilinadi — begona odam
tugmani bossa, post chiqmaydi.

---

## 8. Sifat nazorati qanday ishlaydi

Quality Agent ikki qatlamda tekshiradi:

1. **Qoidalar** (tarmoqsiz): uzunlik, havolalar soni, taqiqlangan iboralar,
   hashtaglar, Markdown sarlavhalari.
2. **LLM-review** (`use_llm: true`): faktlar materialga mos keladimi, til toza mi,
   hook va CTA bormi, xavfli maslahat yo'qmi.

Verdikt `fix` yoki `regenerate` bo'lsa — post Writer'ga izoh bilan qaytadi.
`max_retries` tugagach status `needs_review` bo'ladi va **kanalga chiqmaydi**.

---

## 9. Doimiy ishlash (deploy)

> **Muhim:** bu bot Claude Cowork sandbox'ida ishlay olmaydi. O'sha muhitda tashqi
> tarmoq oq ro'yxat bilan cheklangan: `api.telegram.org` va `api.tavily.com` ga
> chiqish yopiq (proxy 403 qaytaradi). Cowork'da kodni yozish, sozlash va testlarni
> yurgizish mumkin — lekin postni kanalga chiqarish uchun bot boshqa joyda ishlashi kerak.

### A. GitHub Actions (bepul, server kerak emas) — tavsiya etiladi

`.github/workflows/` ichida ikkita tayyor workflow bor:

| Fayl | Nima qiladi |
|---|---|
| `post.yml` | Jadval bo'yicha post tayyorlaydi (har rubrika o'z cron'i bilan) |
| `approve.yml` | Har 15 daqiqada ✅/✏️/❌ tugmalarini tekshiradi |

**O'rnatish:**

1. Loyihani GitHub'ga yuklang (`.env` yuklanmasin — u `.gitignore` da).
2. Repo → **Settings → Secrets and variables → Actions → New repository secret**.
   Beshta secret qo'shing:

   | Secret nomi | Qiymati |
   |---|---|
   | `ANTHROPIC_API_KEY` | `sk-ant-...` |
   | `TAVILY_API_KEY` | `tvly-...` |
   | `TELEGRAM_BOT_TOKEN` | `1234:AA...` |
   | `TELEGRAM_CHANNEL_ID` | `@kanal_nomi` |
   | `TELEGRAM_REVIEW_CHAT_ID` | sizning ID raqamingiz |

3. Repo → **Settings → Actions → General → Workflow permissions** →
   **Read and write permissions** ni yoqing (holat bazasini saqlash uchun).
4. **Actions** bo'limiga o'ting → `Move Space — post tayyorlash` → **Run workflow** →
   rubrikani tanlab qo'lda sinab ko'ring.

**Bilib qo'ying:**

- GitHub cron **UTC**'da. Toshkent = UTC+5, `post.yml` ichida allaqachon hisoblangan
  (07:00 Toshkent = `0 2 * * ...`). Jadvalni o'zgartirsangiz — 5 soat ayirishni unutmang.
- GitHub cron aniq daqiqada emas, 5–15 daqiqa kechikib ishga tushishi mumkin. Kontent
  posti uchun bu muammo emas.
- Ochiq (public) repoda Actions bepul va cheksiz; yopiq repoda oyiga 2000 daqiqa —
  u holda `approve.yml` dagi `*/15` ni `*/30` ga o'zgartiring.
- `data/state.db` har run'dan keyin repo'ga commit qilinadi — takroriy mavzu chiqmasligi
  uchun. Ichida sir yo'q, faqat mavzular va statuslar.

### B. VPS yoki doim yoqiq kompyuter

```bash
python cli.py schedule                  # rubrikalardagi cron bo'yicha
python -m scheduler.approval_bot        # tasdiq tugmalari uchun (alohida jarayon)
```

systemd yoki `docker compose` bilan doim yoqiq turishi kerak.

### C. Tizim cron'i (eng sodda)

```cron
0 7 * * 1,4 cd /opt/movespace_bot && .venv/bin/python cli.py run -r running
*/5 * * * * cd /opt/movespace_bot && .venv/bin/python -m scheduler.approval_bot --once
```

---

## 10. Testlar

```bash
python -m pytest -q
```

Testlar tarmoqqa chiqmaydi — `fake` providerlar ishlatiladi, shuning uchun
kalitlarsiz ham ishlaydi va pul sarflamaydi.

---

## 11. Xavfsizlik

- Kalitlar faqat `.env` da, kod ichida emas. `.env` — `.gitignore` da.
- `python cli.py doctor` qaysi kalit yetishmayotganini aytadi.
- Standart rejim `review` — post sizning ko'zingizdan o'tmasdan kanalga chiqmaydi.

---

## Keyingi qadamlar

- [ ] `config/style/samples.md` ga o'zingizning 3–5 ta real postingizni qo'ying
- [ ] Anthropic hisobiga kredit qo'shish (kalit bor, lekin balans 0 bo'lsa API ishlamaydi)
- [ ] GitHub'ga yuklab, 5 ta secret qo'shish va `Run workflow` bilan sinash
- [ ] Bir hafta `review` rejimida yuring, sifat barqaror bo'lgach ba'zi rubrikalarni
      `mode: auto` ga o'tkazing (`move_uz` dan tashqari)
- [ ] Image agentni jonli Gemini API'da sinash, so'ng `image_required: true`
