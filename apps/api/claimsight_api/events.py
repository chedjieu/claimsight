"""In-process pub/sub so sync pipeline code can notify SSE/WebSocket clients."""

from __future__ import annotations

from queue import Full, Queue
from typing import Any

_SUBS: list[Queue] = []


def subscribe() -> Queue:
    q: Queue = Queue(maxsize=64)
    _SUBS.append(q)
    return q


def unsubscribe(q: Queue) -> None:
    if q in _SUBS:
        _SUBS.remove(q)


def publish(event: dict[str, Any]) -> None:
    for q in list(_SUBS):
        try:
            q.put_nowait(event)
        except Full:
            continue
