"""인메모리 TTL 응답 캐시 — 읽기 전용 집계 엔드포인트 가속.

데이터는 ETL(`python -m jobs.run --job daily`)이 **하루 1회**만 갱신한다. 그런데 피드·
카테고리·인물 목록 같은 집계 응답을 매 요청마다 DB에서 재계산하고 있어, 같은 결과를
반복 계산하는 낭비가 크다. 이 모듈은 그 응답을 프로세스 메모리에 짧게 캐싱한다.

무효화 전략(🟡 의도적으로 단순):
  ETL 은 API 와 **별도 프로세스/컨테이너**라 잡에서 이 캐시를 직접 비울 수 없다.
  대신 짧은 TTL(기본 30분)로 만료시킨다 — 일일 갱신 뒤 늦어도 TTL 안에 새 데이터가
  반영되고, 그 사이엔 직전 스냅샷을 보여준다(법안·표결 데이터라 분 단위 신선도 불필요).
  Cloud Run 다중 인스턴스는 각자 캐싱한다(인스턴스당 키마다 TTL 1회만 재계산 → 무해).

안전성:
  캐시에 담기는 값은 라우터가 그 자리에서 만든 Pydantic 모델이며, 반환 후 누구도
  변형하지 않는다(FastAPI 는 매 요청 직렬화만 함). 따라서 공유 참조 캐싱이 안전하다.
"""
from __future__ import annotations

import functools
import threading
import time
from collections import OrderedDict

from sqlalchemy.orm import Session

_DEFAULT_TTL = 1800  # 30분 — 일일 갱신 대비 충분히 짧음
_DEFAULT_MAXSIZE = 256

_MISS = object()
_caches: list["_TTLCache"] = []  # clear_all() 용 레지스트리


class _TTLCache:
    """스레드 안전 LRU+TTL 캐시(동기 def 라우터가 스레드풀에서 도므로 락 필요)."""

    def __init__(self, maxsize: int, ttl: float) -> None:
        self.maxsize = maxsize
        self.ttl = ttl
        self._store: "OrderedDict[object, tuple[float, object]]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: object) -> object:
        now = time.monotonic()
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return _MISS
            expires_at, value = item
            if expires_at < now:
                del self._store[key]
                return _MISS
            self._store.move_to_end(key)  # LRU 갱신
            return value

    def set(self, key: object, value: object) -> None:
        now = time.monotonic()
        with self._lock:
            self._store[key] = (now + self.ttl, value)
            self._store.move_to_end(key)
            while len(self._store) > self.maxsize:
                self._store.popitem(last=False)  # 가장 오래된 것부터 축출

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


def cached(ttl: float = _DEFAULT_TTL, maxsize: int = _DEFAULT_MAXSIZE):
    """라우터 핸들러용 TTL 캐시 데코레이터.

    `@router.get(...)` **아래**에 둔다(FastAPI 가 원본 시그니처로 의존성을 주입하도록
    functools.wraps 로 시그니처를 보존). 캐시 키는 DB 세션을 제외한 쿼리 인자들이다.
    """
    cache = _TTLCache(maxsize, ttl)
    _caches.append(cache)

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # 캐시 키 — Session(요청마다 다른 객체)은 제외, 나머지 쿼리 인자만.
            key = (
                tuple(a for a in args if not isinstance(a, Session)),
                tuple(sorted(
                    (k, v) for k, v in kwargs.items() if not isinstance(v, Session)
                )),
            )
            hit = cache.get(key)
            if hit is not _MISS:
                return hit
            value = fn(*args, **kwargs)
            cache.set(key, value)
            return value

        return wrapper

    return decorator


def clear_all() -> None:
    """등록된 모든 캐시 비우기 — 같은 프로세스 내 수동 무효화용(예: 내부 엔드포인트)."""
    for cache in _caches:
        cache.clear()
