"""Small reusable helpers: retry decorator, timing context manager, batching generator."""
from __future__ import annotations

import functools
import logging
import random
import time
from contextlib import contextmanager
from itertools import islice
from typing import Callable, Iterable, Iterator, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")

log = logging.getLogger(__name__)


def retry(
    attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Retry with exponential backoff + jitter. Only for *transient* errors."""

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            for attempt in range(1, attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    if attempt == attempts:
                        raise
                    delay = min(max_delay, base_delay * 2 ** (attempt - 1)) * random.uniform(0.5, 1.0)
                    log.warning("%s failed (%s), retry %d/%d in %.2fs",
                                fn.__name__, exc, attempt, attempts - 1, delay)
                    time.sleep(delay)
            raise AssertionError("unreachable")

        return wrapper

    return decorator


@contextmanager
def timed(label: str) -> Iterator[dict[str, float]]:
    result = {"seconds": 0.0}
    start = time.perf_counter()
    try:
        yield result
    finally:
        result["seconds"] = time.perf_counter() - start
        log.info("%s took %.3fs", label, result["seconds"])


def batched(items: Iterable[T], size: int) -> Iterator[list[T]]:
    """Yield lists of up to `size` items (itertools.batched exists from Python 3.12)."""
    if size < 1:
        raise ValueError("size must be >= 1")
    it = iter(items)
    while chunk := list(islice(it, size)):
        yield chunk
