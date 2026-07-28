from __future__ import annotations

from collections.abc import Callable
from time import sleep
from typing import TypeVar

from trading_assistant.market_data.base import ProviderRequestError


T = TypeVar("T")


def run_with_retry(
    operation: Callable[[], T],
    *,
    max_attempts: int = 3,
    base_delay_seconds: float = 0.5,
    sleeper: Callable[[float], None] = sleep,
) -> tuple[T, int]:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    last_error: ProviderRequestError | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return operation(), attempt
        except ProviderRequestError as exc:
            last_error = exc
            if not exc.retryable or attempt == max_attempts:
                raise
            sleeper(base_delay_seconds * (2 ** (attempt - 1)))

    if last_error is not None:
        raise last_error
    raise RuntimeError("Retry loop exited without a result")
