"""Jonli o'z-o'zini tekshirish: har bir tashqi xizmatga bitta kichik so'rov.

`python cli.py doctor --live` shu modulni chaqiradi. Natija konsolga chiqadi va
(Telegram ishlayotgan bo'lsa) tasdiq chatiga ham yuboriladi — shunda GitHub
loglarini ochish shart emas.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from config.settings import Settings, get_settings


@dataclass
class Check:
    name: str
    ok: bool
    detail: str

    def line(self) -> str:
        return f"{'✅' if self.ok else '❌'} {self.name}: {self.detail}"


async def check_llm(s: Settings) -> Check:
    from providers.llm import get_llm_provider

    try:
        llm = get_llm_provider(settings=s)
    except Exception as exc:  # noqa: BLE001
        return Check("LLM", False, f"provider yaratilmadi: {exc}")

    try:
        out = await llm.complete(
            "Faqat 'ishladi' deb javob ber.", max_tokens=20, temperature=0
        )
        return Check(f"LLM ({llm.name})", True, f"javob keldi: {out.strip()[:40]!r}")
    except Exception as exc:  # noqa: BLE001
        return Check(f"LLM ({llm.name})", False, str(exc)[:400])


async def check_search(s: Settings) -> Check:
    from providers.search import get_search_provider

    try:
        provider = get_search_provider(settings=s)
        results = await provider.search("running training tips", max_results=2)
        return Check(f"Qidiruv ({provider.name})", True, f"{len(results)} ta manba topildi")
    except Exception as exc:  # noqa: BLE001
        return Check("Qidiruv", False, str(exc)[:400])


async def check_telegram(s: Settings) -> list[Check]:
    import httpx

    if not s.telegram_bot_token:
        return [Check("Telegram", False, "TELEGRAM_BOT_TOKEN yo'q")]

    base = f"https://api.telegram.org/bot{s.telegram_bot_token}"
    checks: list[Check] = []
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            me = (await c.get(f"{base}/getMe")).json()
            if not me.get("ok"):
                return [Check("Telegram bot", False, str(me.get("description"))[:200])]
            bot = me["result"]
            checks.append(Check("Telegram bot", True, f"@{bot['username']}"))

            if not s.telegram_channel_id:
                checks.append(Check("Kanal", False, "TELEGRAM_CHANNEL_ID yo'q"))
                return checks

            chat = (await c.post(f"{base}/getChat",
                                 json={"chat_id": s.telegram_channel_id})).json()
            if not chat.get("ok"):
                checks.append(Check("Kanal", False, str(chat.get("description"))[:200]))
                return checks
            checks.append(Check("Kanal", True, f"{chat['result'].get('title')}"))

            m = (await c.post(f"{base}/getChatMember",
                              json={"chat_id": s.telegram_channel_id,
                                    "user_id": bot["id"]})).json()
            if m.get("ok"):
                r = m["result"]
                can_post = r.get("can_post_messages")
                ok = r.get("status") == "administrator" and can_post is not False
                checks.append(Check("Bot huquqi", ok,
                                    f"{r.get('status')}, post yuborish: {can_post}"))
            else:
                checks.append(Check("Bot huquqi", False, str(m.get("description"))[:200]))
    except Exception as exc:  # noqa: BLE001
        checks.append(Check("Telegram", False, str(exc)[:300]))
    return checks


async def run_live_checks(s: Settings | None = None) -> list[Check]:
    s = s or get_settings()
    llm, search, telegram = await asyncio.gather(
        check_llm(s), check_search(s), check_telegram(s)
    )
    return [llm, search, *telegram]


async def report_to_telegram(s: Settings, checks: list[Check]) -> bool:
    """Natijani tasdiq chatiga yuboradi. Yuborilsa True."""
    import httpx

    if not (s.telegram_bot_token and s.telegram_review_chat_id):
        return False

    ok_count = sum(1 for c in checks if c.ok)
    head = "✅ Hammasi joyida" if ok_count == len(checks) else "⚠️ Muammo bor"
    text = (
        f"<b>{head}</b>  ({ok_count}/{len(checks)})\n\n"
        + "\n".join(c.line() for c in checks)
    )
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage",
                json={"chat_id": s.telegram_review_chat_id,
                      "text": text[:4000], "parse_mode": "HTML"},
            )
        return r.json().get("ok", False)
    except Exception:  # noqa: BLE001
        return False
