"""In-process fan-out for the operations console.

The billing consumer and the HTTP server share one process, so a new
transaction can be pushed to every open Server-Sent Events client without
another broker.
"""

import asyncio
from typing import Any

_subscribers: set[asyncio.Queue] = set()


def subscribe() -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue(maxsize=32)
    _subscribers.add(queue)
    return queue


def unsubscribe(queue: asyncio.Queue) -> None:
    _subscribers.discard(queue)


def publish(event: str, data: dict[str, Any]) -> None:
    stale: list[asyncio.Queue] = []
    for queue in list(_subscribers):
        try:
            queue.put_nowait((event, data))
        except asyncio.QueueFull:
            stale.append(queue)
    for queue in stale:
        _subscribers.discard(queue)
