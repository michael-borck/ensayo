"""Per-key sliding-window rate limiting for self-service auth endpoints.

Ensayo is single-process (one uvicorn; ADR-0002), so an in-process limiter is
sufficient and avoids a ``slowapi`` dependency. Thread-safe (FastAPI runs sync
endpoints in a threadpool).

Granularity is **per-email**, never per-IP: a teaching demo commonly has a whole
cohort behind one NAT IP, so IP limits would block legitimate users. Login is
not rate-limited at all — per-account lockout (see
``registration.is_locked_out``) handles brute force without DoSing a shared-IP
cohort. Edge-level IP throttling, if ever needed, belongs in Cloudflare.

Only the low-frequency, pre-login endpoints (verify / resend) are limited, and
only per email. Registration is gated by the domain allowlist + once-per-email.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, max_calls: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            dq = self._hits[key]
            while dq and dq[0] <= cutoff:
                dq.popleft()
            if len(dq) >= max_calls:
                return False
            dq.append(now)
            return True

    def reset_all(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()

# (max_calls, window_seconds), enforced per email.
LIMITS = {
    "verify": (10, 900),   # 10 code checks / 15 min / email
    "resend": (3, 3600),   # 3 new codes / hour / email
}


def check(action: str, email: str | None) -> bool:
    """Enforce the named per-email limit. Returns False when over budget."""
    if action not in LIMITS or not email:
        return True
    max_calls, window = LIMITS[action]
    return limiter.allow(f"{action}:{email.strip().lower()}", max_calls, window)
