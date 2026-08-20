"""Cron bo'yicha rubrikalarni avtomatik ishga tushirish.

Ishga tushirish:
    python cli.py schedule
yoki
    python -m scheduler.runner

Har bir rubrikaning `schedule.cron` maydoni bo'yicha ish rejalashtiriladi.
Server doim yoqiq turishi kerak (systemd / docker / pm2).
Muqobil variant: APScheduler o'rniga tizim cron'idan
`python cli.py run -r <rubrika>` ni chaqirish.
"""

from __future__ import annotations

import asyncio
import logging

from config.settings import get_settings
from core.logging_setup import setup_logging
from core.pipeline import Pipeline
from core.rubric import RubricConfig, load_all_rubrics

log = logging.getLogger("scheduler")


async def _run_rubric_job(rubric_key: str) -> None:
    from core.rubric import load_rubric

    try:
        rubric = load_rubric(rubric_key)          # har safar yangidan o'qiladi
        ctx = await Pipeline(rubric).run()
        log.info("[%s] tugadi: %s", rubric_key, ctx.status.value)
    except Exception as exc:  # noqa: BLE001
        log.error("[%s] xato: %s", rubric_key, exc, exc_info=True)


def _register(scheduler, rubric: RubricConfig, timezone: str) -> bool:
    from apscheduler.triggers.cron import CronTrigger

    if not rubric.cron:
        log.warning("[%s] cron ko'rsatilmagan — o'tkazib yuborildi", rubric.key)
        return False

    tz = rubric.schedule.get("timezone", timezone)
    scheduler.add_job(
        _run_rubric_job,
        CronTrigger.from_crontab(rubric.cron, timezone=tz),
        args=[rubric.key],
        id=f"rubric:{rubric.key}",
        name=rubric.name,
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
        max_instances=1,
    )
    log.info("[%s] rejalashtirildi: %s (%s)", rubric.key, rubric.cron, tz)
    return True


def main() -> int:
    settings = get_settings()
    setup_logging(settings.log_level)

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError:
        log.error(
            "APScheduler o'rnatilmagan. `pip install apscheduler` qiling yoki "
            "tizim cron'idan `python cli.py run -r <rubrika>` ni chaqiring."
        )
        return 1

    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    count = sum(_register(scheduler, r, settings.timezone) for r in load_all_rubrics())

    if not count:
        log.error("Rejalashtiriladigan rubrika topilmadi")
        return 1

    scheduler.start()
    log.info("Scheduler ishga tushdi (%d ta rubrika). To'xtatish: Ctrl+C", count)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        log.info("To'xtatilmoqda...")
        scheduler.shutdown(wait=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
