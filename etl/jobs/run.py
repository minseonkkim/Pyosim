"""잡 러너 골격 — 스케줄러(cron / Cloud Scheduler)가 트리거하는 진입점.

사용: python -m jobs.run --job <name>
등록된 잡만 실행. 실제 수집 로직은 Phase 1-2 에서 구현.
"""
import argparse
import sys

# 잡 레지스트리: 이름 -> 호출가능. Phase 진행하며 채운다.
JOBS: dict[str, "callable"] = {}


def register(name: str):
    def deco(fn):
        JOBS[name] = fn
        return fn

    return deco


@register("ping")
def _ping() -> None:
    """동작 확인용 더미 잡."""
    print("pong — ETL 러너 정상 동작")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="표심 ETL 잡 러너")
    parser.add_argument("--job", required=True, help=f"실행할 잡 이름. 등록됨: {', '.join(JOBS) or '(없음)'}")
    args = parser.parse_args(argv)

    job = JOBS.get(args.job)
    if job is None:
        print(f"알 수 없는 잡: {args.job}. 등록됨: {', '.join(JOBS)}", file=sys.stderr)
        return 2
    job()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
