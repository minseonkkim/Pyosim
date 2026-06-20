"""잡 러너 — 스케줄러(cron / Cloud Scheduler)가 트리거하는 진입점.

사용:
  python -m jobs.run --job ping
  python -m jobs.run --job members
  python -m jobs.run --job photos               # 의원 사진(ALLNAMEMBER NAAS_PIC)
  python -m jobs.run --job bills
  python -m jobs.run --job vote_records --limit 20
  python -m jobs.run --job propose_dates --limit 50   # likms 상세 '제안일자' → 발의일(대안 보강)
  python -m jobs.run --job bill_content --limit 50    # likms 의안원문 본문 수집
  python -m jobs.run --job bill_summary --limit 50    # 본문 → 좋은점/문제점 AI 요약
  python -m jobs.run --job bills --dry-run            # 미기록(미리보기, DB 연결은 필요)

키는 etl/.env 의 ASSEMBLY_API_KEY·GEMINI_API_KEY, DB 는 DATABASE_URL.
"""
from __future__ import annotations

import argparse
import sys

# 잡 레지스트리: 이름 -> 핸들러(args -> None)
JOBS: dict[str, "callable"] = {}


def register(name: str):
    def deco(fn):
        JOBS[name] = fn
        return fn

    return deco


@register("ping")
def _ping(args) -> None:
    """동작 확인용 더미 잡."""
    print("pong — ETL 러너 정상 동작")


def _build_client():
    from config import settings
    from clients.assembly import AssemblyClient

    return AssemblyClient(settings.assembly_api_key)


def _build_ofd_client():
    from config import settings
    from clients.openfiscal import OpenFiscalClient

    return OpenFiscalClient(settings.ofd_api_key)


def _build_session():
    from jobs.db import make_session_factory

    return make_session_factory()()


@register("members")
def _members(args) -> None:
    from jobs import ingest

    session = _build_session()
    try:
        stats = ingest.run_members(
            session, _build_client(), age=args.age, dry_run=args.dry_run, limit=args.limit
        )
    finally:
        session.close()
    print(f"members 완료{' (dry-run)' if args.dry_run else ''}: {stats}")


@register("photos")
def _photos(args) -> None:
    from jobs import ingest

    session = _build_session()
    try:
        stats = ingest.run_photos(
            session, _build_client(), age=args.age, dry_run=args.dry_run, limit=args.limit
        )
    finally:
        session.close()
    print(f"photos 완료{' (dry-run)' if args.dry_run else ''}: {stats}")


@register("bills")
def _bills(args) -> None:
    from jobs import ingest

    session = _build_session()
    try:
        stats = ingest.run_bills(
            session, _build_client(), age=args.age, dry_run=args.dry_run, limit=args.limit
        )
    finally:
        session.close()
    print(f"bills 완료{' (dry-run)' if args.dry_run else ''}: {stats}")


@register("vote_records")
def _vote_records(args) -> None:
    from jobs import ingest

    session = _build_session()
    try:
        stats = ingest.run_vote_records(
            session, _build_client(), age=args.age, dry_run=args.dry_run, limit=args.limit
        )
    finally:
        session.close()
    print(f"vote_records 완료{' (dry-run)' if args.dry_run else ''}: {stats}")


@register("proposers")
def _proposers(args) -> None:
    from jobs import ingest

    session = _build_session()
    try:
        stats = ingest.run_proposers(
            session, _build_client(), age=args.age, dry_run=args.dry_run, limit=args.limit
        )
    finally:
        session.close()
    print(f"proposers 완료{' (dry-run)' if args.dry_run else ''}: {stats}")


@register("propose_dates")
def _propose_dates(args) -> None:
    # likms 의안 상세 '제안일자' → Bill.proposed_date (표결된 대안 등 발의일 누락분 보강)
    from jobs import bill_propose_date

    session = _build_session()
    try:
        stats = bill_propose_date.run_propose_dates(
            session, dry_run=args.dry_run, limit=args.limit
        )
    finally:
        session.close()
    print(f"propose_dates 완료{' (dry-run)' if args.dry_run else ''}: {stats}")


@register("bill_content")
def _bill_content(args) -> None:
    # likms 의안원문(HWP)에서 제안이유·주요내용 수집 (API 아님 — 스크래핑이라 client 불필요)
    from jobs import bill_content

    session = _build_session()
    try:
        stats = bill_content.run_bill_content(
            session, dry_run=args.dry_run, limit=args.limit
        )
    finally:
        session.close()
    print(f"bill_content 완료{' (dry-run)' if args.dry_run else ''}: {stats}")


@register("bill_summary")
def _bill_summary(args) -> None:
    # 제안이유·주요내용 원문 → 좋은점/문제점(양쪽 대칭) AI 생성 (Gemini, client 불필요)
    from jobs import bill_summary

    session = _build_session()
    try:
        stats = bill_summary.run_bill_summary(
            session, dry_run=args.dry_run, limit=args.limit
        )
    finally:
        session.close()
    print(f"bill_summary 완료{' (dry-run)' if args.dry_run else ''}: {stats}")


@register("budget")
def _budget(args) -> None:
    # 열린재정 OPFI165(결산)+OPFI172(본예산) → frontend/lib/budget-data.json (세금 계산기)
    from jobs import budget

    stats = budget.run_budget(
        _build_ofd_client(), year=args.year, dry_run=args.dry_run
    )
    print(f"budget 완료{' (dry-run)' if args.dry_run else ''}: {stats}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="표심 ETL 잡 러너")
    parser.add_argument("--job", required=True, help=f"실행할 잡. 등록됨: {', '.join(JOBS)}")
    parser.add_argument("--age", default="22", help="국회 대수 (기본 22)")
    parser.add_argument("--limit", type=int, default=None, help="처리 건수 상한")
    parser.add_argument("--year", type=int, default=None, help="회계연도 (budget 잡; 미지정 시 최근 결산연도)")
    parser.add_argument("--dry-run", action="store_true", help="DB 미기록(미리보기)")
    args = parser.parse_args(argv)

    job = JOBS.get(args.job)
    if job is None:
        print(f"알 수 없는 잡: {args.job}. 등록됨: {', '.join(JOBS)}", file=sys.stderr)
        return 2
    job(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
