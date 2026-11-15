"""In-memory rate limits: POST /api/ask (spends money on every question), and a looser one for the data
routes and /mcp/ (each uncached request can force fresh upstream fetches that use up a provider's allowance)."""
import math
import threading
import time
from collections import deque

PER_CLIENT, CLIENT_WINDOW_S = 30, 60  # the voice widget: many visitors share a few ElevenLabs addresses
PER_CLIENT_HOUR, CLIENT_HOUR_S = 150, 3600  # so one client cannot spend the whole global cap
GLOBAL, GLOBAL_WINDOW_S = 200, 3600
DATA_PER_CLIENT, DATA_PER_CLIENT_HOUR = 120, 1200  # same windows; no overall cap, so one client can't lock out all
MAX_CLIENTS = 10_000

# ponytail: three caps for /api/ask (30/min and 150/hour per client, 200/hour overall), two for data
# (120/min and 1,200/hour per client). The counters live in one serverless instance's memory, so this slows a
# single abuser but is not a global cap (each warm instance counts on its own, and a cold start resets it).
# Each client keeps at most one hour of timestamps (150 for ask, 1,200 for data).
# Upgrade: a Vercel Firewall rate-limit rule, or a shared store such as Redis.
_lock = threading.Lock()
_clients: dict[str, deque] = {}
_all: deque = deque()
_data_clients: dict[str, deque] = {}


def _expire(q: deque, before: float) -> None:
    while q and q[0] <= before:
        q.popleft()


def _wait(until: float, now: float) -> int:
    return max(1, math.ceil(until - now))


def _check(clients: dict, everyone: deque | None, per_min: int, per_hour: int, cap: int,
           client: str, now: float | None) -> int:
    now = time.monotonic() if now is None else now
    with _lock:
        until = 0
        if everyone is not None:
            _expire(everyone, now - GLOBAL_WINDOW_S)
            until = everyone[0] + GLOBAL_WINDOW_S if len(everyone) >= cap else 0  # the longest wait, not one then another
        q = clients.get(client)
        if q is not None:
            _expire(q, now - CLIENT_HOUR_S)
            until = max(until, q[0] + CLIENT_HOUR_S if len(q) >= per_hour else 0,
                        q[-per_min] + CLIENT_WINDOW_S if len(q) >= per_min else 0)
        if until > now:
            return _wait(until, now)
        if q is None:
            if len(clients) >= MAX_CLIENTS:
                for k in [k for k, v in clients.items() if not v or v[-1] <= now - CLIENT_HOUR_S]:
                    del clients[k]
                while len(clients) >= MAX_CLIENTS:  # still full of live clients: drop the oldest seen
                    del clients[next(iter(clients))]
            q = clients[client] = deque()
        q.append(now)
        if everyone is not None:
            everyone.append(now)
        return 0


def check(client: str, now: float | None = None) -> int:
    """0 if this question is allowed (and counts it), else the seconds to wait. Refused requests don't count."""
    return _check(_clients, _all, PER_CLIENT, PER_CLIENT_HOUR, GLOBAL, client, now)


def check_data(client: str, now: float | None = None) -> int:
    """Same as check, for GET /api/series, GET /api/trend and /mcp/: a separate, looser per-client budget."""
    return _check(_data_clients, None, DATA_PER_CLIENT, DATA_PER_CLIENT_HOUR, 0, client, now)


def reset() -> None:
    with _lock:
        _clients.clear()
        _all.clear()
        _data_clients.clear()
