# Admin panel + Sayt — reja (qoralama)

> Maqsad: adminkaga kirib **"Post tayyorlash"** bosilganda, xuddi botdagidek
> post tayyorlanadi va tasdiqlangach **ham Telegram kanalga**, **ham saytga**
> bir vaqtda chiqadi. Bot ham, adminka ham baravar ishlab turaveradi.

---

## 1. Yaxshi xabar: yarmi allaqachon tayyor

Kod ataylab shu kun uchun tuzilgan — hech narsa qaytadan yozilmaydi:

| Kerak bo'lgan narsa | Kodda hozir bor |
|---|---|
| Bot va adminka uchun bitta mantiq | `core/service.py → ContentService` (create_post, list_posts, publish, reject) |
| Bir postni ham TG, ham saytga chiqarish | `agents/publisher_agent.py` — `publish_to` ro'yxati bo'yicha aylanadi; `_target_telegram` va `_target_web` bor |
| Postni turli formatga o'girish | `core/render.py` — `render_telegram`, `render_markdown`, `render_html` |
| Sayt/adminka uchun tuzilgan kontent | `PostContent` (`content_json` bazada saqlanadi) |
| Bazada sayt ustuni | `posts.web_path`, `posts.content_json` allaqachon bor |

Ya'ni asosiy ish — shu tayyor mantiq ustiga **HTTP API**, **adminka oynasi** va
**ochiq sayt** qo'shish. Post yozish "aqli"ga tegilmaydi.

---

## 2. Umumiy ko'rinish

```
                       ┌─────────────────────────────┐
   Telegram bot ──────►│                             │
                       │        ContentService       │──► Pipeline (post yozadi)
   Admin panel ───────►│   (bitta biznes-mantiq)     │──► Storage (SQLite/Postgres)
     (brauzer)         │                             │──► Publisher ─┬─► Telegram kanal
                       └─────────────────────────────┘               └─► Sayt (DB)
                                    ▲                                        │
                                    │ HTTP API (yangi)                       ▼
                             Admin panel (Nuxt SPA)                    Ochiq sayt (Nuxt)
```

Uch yangi qism: **(A) Backend API**, **(B) Admin panel**, **(C) Ochiq sayt**.

---

## 3. Qismlar

### A. Backend API (FastAPI) — tayyor mantiq ustiga qobiq
Python'da yoziladi, chunki `ContentService`ni to'g'ridan-to'g'ri chaqiradi (til bir xil).

Endpointlar (taxminiy):
- `POST /api/auth/login` — adminka kirishi (parol → token)
- `GET  /api/rubrics` — rubrikalar ro'yxati (tugmalar uchun)
- `POST /api/posts` — **"Post tayyorlash"** (rubrika beriladi → pipeline ishga tushadi)
- `GET  /api/posts` — barcha postlar + holati (kutilmoqda / chiqqan / bekor)
- `GET  /api/posts/{id}` — bitta post: matni, sayt ko'rinishi (HTML preview)
- `POST /api/posts/{id}/publish` — tasdiqlash → **TG + sayt** ga chiqaradi
- `POST /api/posts/{id}/reject` — bekor qilish
- `POST /api/posts/{id}/rewrite` — qayta yozdirish
- `GET  /api/site/posts` va `/api/site/posts/{slug}` — ochiq sayt uchun (tokensiz)

### B. "Post tayyorlash" muammosi — vaqt
Pipeline ~1-2 daqiqa ishlaydi (material izlash + yozish + sifat). HTTP so'rov
buncha kutolmaydi. Yechim: **fon vazifasi (job)** —
- Tugma bosilganda API darrov `job_id` qaytaradi, pipeline fonda ishlaydi.
- Adminka har 2-3 soniyada holatni so'rab turadi (yoki WebSocket/SSE bilan jonli).
- Tayyor bo'lgach post preview + tasdiq tugmalari chiqadi.
- Bazaga `jobs` jadvali qo'shiladi (yoki mavjud `posts.status` orqali kuzatiladi).

### C. Sayt uchun chiqarish (`_target_web` ni takomillashtirish)
Hozir `_target_web` markdown faylni `data/site/` ga yozadi. Reja:
- Postni **bazaga** (`content_json` + `status=published` + `published_at`) yozadi —
  ochiq sayt API shu yerdan o'qiydi. Fayl ham qolishi mumkin (zaxira/statik).
- Rubrikada `publish_to: [telegram, web]` qilinadi → tasdiqlashda **ikkalasiga**
  ketadi. Kod tayyor: `_publish_all` ro'yxat bo'yicha aylanadi.

### D. Admin panel (frontend — Nuxt 3 SPA)
Sizga tanish stack (Nuxt 3 + Tailwind + Pinia):
- **Kirish sahifasi** (login).
- **Bosh oyna:** postlar ro'yxati + holat belgilar (✅ chiqqan / ⏳ kutilmoqda / ❌ bekor).
- **"📝 Post tayyorlash" tugmasi:** rubrika tanlanadi → progress ko'rsatiladi → preview.
- **Ko'rik amallari:** ✅ Chiqarish (TG+sayt) / ✏️ Qayta yozish / ❌ Bekor.
- **Rubrikalar sahifasi** (jadval vaqtlarini ko'rish; keyinroq tahrirlash).

### E. Ochiq sayt (frontend)
- Chiqqan postlar ro'yxati + har biriga alohida sahifa (`/{rubrika}/{slug}`).
- `render_html` yoki `content_json`dan chiroyli sahifa yasaladi.
- SEO uchun server-render (Nuxt SSR) yoki statik generatsiya.
- Bitta Nuxt loyihada: ochiq yo'llar (sayt) + himoyalangan yo'llar (`/admin`).

---

## 4. Texnik qarorlar (muhokama uchun)

1. **Baza — SQLite'da qolamizmi yoki Postgres?**
   Hozir bot+scheduler bitta SQLite bazaga yozadi. Web API 3-yozuvchi bo'ladi —
   SQLite'ni **WAL rejimi**ga o'tkazish kifoya qiladi (kam yuk uchun). Yuk oshsa
   yoki keyinchalik ko'p foydalanuvchi bo'lsa → **Postgres** (SERVER.md'da ham
   shunday rejalashtirilgan, 4 GB RAM yetadi). Tavsiya: **avval SQLite+WAL**,
   keyin kerak bo'lsa Postgres.

2. **Kirish (auth).** Boshida bitta admin (siz) yetadi — parol `.env`da, token
   (JWT yoki session). Keyin ko'p admin kerak bo'lsa `users` jadvali qo'shiladi.

3. **Backend framework.** **FastAPI** (async — mavjud `async` pipeline'ga mos,
   Python — mantiq qayta yozilmaydi). `requirements.txt`ga `fastapi`, `uvicorn`
   qo'shiladi.

4. **Domen va HTTPS.** Sayt uchun domen kerak (masalan `movespace.uz`).
   Serverga **Caddy** yoki **Nginx** + Let's Encrypt (bepul TLS) qo'yiladi.

5. **Deploy.** Yangi systemd xizmati `movespace-web` (uvicorn). Frontend build
   qilinib, Caddy/Nginx orqali beriladi. Bot va scheduler o'zgarishsiz qoladi.

---

## 5. Bosqichlar (milestone'lar)

- **1-bosqich — Backend API + sayt chiqishi.** FastAPI, ContentService ustiga
  endpointlar; `_target_web` bazaga yozadigan qilinadi; `publish_to: [telegram, web]`.
  *Natija:* botdan tasdiqlangan post ham TG, ham (API orqali ko'rinadigan) saytga chiqadi.
- **2-bosqich — Admin panel.** Login, postlar ro'yxati, "Post tayyorlash", tasdiq
  tugmalari, jonli progress. *Natija:* brauzerdan botdagi hamma ishni qilish mumkin.
- **3-bosqich — Ochiq sayt.** Chiqqan postlarni chiroyli ko'rsatuvchi sayt + domen + TLS.
- **4-bosqich (ixtiyoriy) — Kengaytmalar.** Rasm (Gemini image), rubrikani
  adminkadan tahrirlash, ko'p admin, Postgres, statistika.

---

## 6. Sizdan javob kerak bo'lgan savollar

1. **Domen** bormi (masalan `movespace.uz`)? Yo'q bo'lsa qaysi nomni olamiz?
2. **Sayt dizayni** — tayyor namuna/rang bormi, yoki men taklif qilaymi?
3. **Adminka kimlar uchun** — faqat sizmi, yoki bir necha kishi kiradimi?
4. **Sayt ko'rinishi** — oddiy blog (ro'yxat + maqola) yetadimi, yoki rubrikalar
   bo'yicha bo'limlar, qidiruv va h.k. kerakmi?
5. **Post tahriri** — chiqishdan oldin matnni adminkada **qo'lda tahrirlash**
   kerakmi, yoki faqat ✅/✏️/❌ yetadimi?
6. **Bosqichlardan** qaysi biridan boshlaymiz (tavsiya: 1-bosqich)?

---

*Bu qoralama. Ko'rib chiqing, o'zgartiring yoki savollarga javob yozib menga
qaytaring — keyin aniq texnik topshiriq va ish rejasiga aylantiramiz.*
