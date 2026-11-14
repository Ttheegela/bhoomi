"""In-memory rate limit for POST /api/ask (the route spends money on every question)."""
import math
import threading
import time
from collections import deque

PER_CLIENT, CLIENT_WINDOW_S = 10, 60
PER_CLIENT_HOUR, CLIENT_HOUR_S = 30, 3600  # so one client cannot spend the whole global cap
GLOBAL, GLOBAL_WINDOW_S = 200, 3600
MAX_CLIENTS = 10_000

# ponytail: three caps (10/min and 30/hour per client, 200/hour overall). The counters live in one
# serverless instance's memory, so this slows a single abuser but is not a global cap (each warm instance
# counts on its own, and a cold start resets it). Each client keeps at most 30 timestamps (one hour).
# Upgrade: a Vercel Firewall rate-limit rule on /api/ask, or a shared store such as Redis.
_lock = threading.Lock()
_clients: dict[str, deque] = {}
_all: deque = deque()


def _expire(q: deque, before: float) -> None:
    while q and q[0] <= before:
        q.popleft()


def _wait(until: float, now: float) -> int:
    return max(1, math.ceil(until - now))


def check(client: str, now: float | None = None) -> int:
    """0 if this question is allowed (and counts it), else the seconds to wait. Refused requests don't count."""
    now = time.monotonic() if now is None else now
    with _lock:
        _expire(_all, now - GLOBAL_WINDOW_S)
        q = _clients.get(client)
        if q is not None:
            _expire(q, now - CLIENT_HOUR_S)
            until = max(q[0] + CLIENT_HOUR_S if len(q) >= PER_CLIENT_HOUR else 0,  # wait for both, not one then the other
                        q[-PER_CLIENT] + CLIENT_WINDOW_S if len(q) >= PER_CLIENT else 0)
            if until > now:
                return _wait(until, now)
        if len(_all) >= GLOBAL:
            return _wait(_all[0] + GLOBAL_WINDOW_S, now)
        if q is None:
            if len(_clients) >= MAX_CLIENTS:
                for k in [k for k, v in _clients.items() if not v or v[-1] <= now - CLIENT_HOUR_S]:
                    del _clients[k]
                while len(_clients) >= MAX_CLIENTS:  # still full of live clients: drop the oldest seen
                    del _clients[next(iter(_clients))]
            q = _clients[client] = deque()
        q.append(now)
        _all.append(now)
        return 0


def reset() -> None:
    with _lock:
        _clients.clear()
        _all.clear()
