#!/usr/bin/env python3
"""Move Space kontent-bot CLI.

Misollar:
    python cli.py rubrics
    python cli.py run --rubric claude_maslahatlar --dry-run
    python cli.py run --rubric yugurish --topic "Yugurishdan keyin tiklanish"
    python cli.py run-all --dry-run
    python cli.py history --rubric claude_maslahatlar
    python cli.py schedule
    python cli.py doctor
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from config.settings import get_settings
from core.logging_setup import setup_logging


def _cmd_rubrics(args: argparse.Namespace) -> int:
    from core.rubric import load_all_rubrics, list_rubric_keys

    keys = list_rubric_keys()
    if not keys:
        print("Rubrika topilmadi. config/rubrics/ ichiga YAML qo'shing.")
        return 1
    print(f"{'KALIT':<24} {'HOLAT':<8} {'CRON':<16} NOMI")
    print("-" * 78)
    for rubric in load_all_rubrics(only_enabled=False):
        state = "yoqilgan" if rubric.enabled else "o'chiq"
        print(f"{rubric.key:<24} {state:<8} {str(rubric.cron or '-'):<16} {rubric.name}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    from core.pipeline import run_rubric

    ctx = asyncio.run(
        run_rubric(args.rubric, topic=args.topic, dry_run=args.dry_run or None)
    )
    _print_result(ctx)
    return 0 if ctx.status.value not in {"failed"} else 1


def _cmd_run_all(args: argparse.Namespace) -> int:
    from core.pipeline import run_all_rubrics

    results = asyncio.run(run_all_rubrics(dry_run=args.dry_run or None))
    for ctx in results:
        _print_result(ctx)
    return 0


def _cmd_history(args: argparse.Namespace) -> int:
    from core.storage import Storage

    rows = Storage(get_settings()).history(args.rubric, limit=args.limit)
    if not rows:
        print("Tarix bo'sh.")
        return 0
    for row in rows:
        print(
            f"{row['created_at']}  {row['rubric']:<20} {row['status']:<18} "
            f"{(row['topic'] or '-')[:50]}"
        )
    return 0


def _cmd_schedule(args: argparse.Namespace) -> int:
    from scheduler.runner import main as scheduler_main

    return scheduler_main()


def _cmd_doctor(args: argparse.Namespace) -> int:
    """Sozlamalar to'g'ri yoki yo'qligini tekshiradi."""
    s = get_settings()
    checks = [
        ("LLM provider", s.llm_provider, bool(
            {"anthropic": s.anthropic_api_key, "openai": s.openai_api_key}.get(s.llm_provider, True)
        )),
        ("Search provider", s.search_provider, s.search_provider != "tavily" or bool(s.tavily_api_key)),
        ("Image provider", s.image_provider, s.image_provider != "gemini" or bool(s.gemini_api_key)),
        ("TTS provider", s.tts_provider, s.tts_provider != "elevenlabs" or bool(s.elevenlabs_api_key)),
        ("Telegram bot token", "bor" if s.telegram_bot_token else "yo'q", bool(s.telegram_bot_token)),
        ("Telegram kanal", s.telegram_channel_id or "yo'q", bool(s.telegram_channel_id)),
        ("Tasdiq chat", s.telegram_review_chat_id or "yo'q", bool(s.telegram_review_chat_id)),
    ]
    print(f"{'TEKSHIRUV':<22} {'QIYMAT':<22} HOLAT")
    print("-" * 60)
    for name, value, ok in checks:
        print(f"{name:<22} {str(value):<22} {'✓' if ok else '✗ kalit yetishmayapti'}")
    print(f"\nData papkasi: {s.data_dir}")
    print(f"DRY_RUN: {s.dry_run}")
    return 0


def _print_result(ctx) -> None:
    print("\n" + "=" * 70)
    print(f"Rubrika : {ctx.rubric_key}")
    print(f"Run ID  : {ctx.run_id}")
    print(f"Holat   : {ctx.status.value}")
    print(f"Mavzu   : {ctx.topic or '-'}")
    if ctx.quality:
        print(f"Sifat   : {ctx.quality.score:.1f} ({ctx.quality.verdict.value})")
        for issue in ctx.quality.issues:
            print(f"   ! {issue}")
    if ctx.errors:
        print("Xatolar :")
        for err in ctx.errors:
            print(f"   - {err}")
    print("-" * 70)
    print(ctx.post_text or "(post yozilmadi)")
    print("=" * 70)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="movespace", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--log-level", default=None, help="DEBUG | INFO | WARNING")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("rubrics", help="Rubrikalar ro'yxati").set_defaults(func=_cmd_rubrics)

    p_run = sub.add_parser("run", help="Bitta rubrika bo'yicha post tayyorlash")
    p_run.add_argument("--rubric", "-r", required=True)
    p_run.add_argument("--topic", "-t", default=None, help="Mavzuni qo'lda berish")
    p_run.add_argument("--dry-run", action="store_true", help="Hech narsa yuborilmaydi")
    p_run.set_defaults(func=_cmd_run)

    p_all = sub.add_parser("run-all", help="Barcha yoqilgan rubrikalar")
    p_all.add_argument("--dry-run", action="store_true")
    p_all.set_defaults(func=_cmd_run_all)

    p_hist = sub.add_parser("history", help="Chiqqan postlar tarixi")
    p_hist.add_argument("--rubric", "-r", default=None)
    p_hist.add_argument("--limit", "-n", type=int, default=20)
    p_hist.set_defaults(func=_cmd_history)

    sub.add_parser("schedule", help="Cron bo'yicha doimiy ishlash").set_defaults(func=_cmd_schedule)
    sub.add_parser("doctor", help="Sozlamalarni tekshirish").set_defaults(func=_cmd_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.log_level or get_settings().log_level)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
