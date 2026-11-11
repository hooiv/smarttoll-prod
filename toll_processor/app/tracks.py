"""Short in-memory trail of recent GPS fixes for the operations console.

This is a read model for the local dashboard, not the system of record.
The toll decision still lives in Redis and the charge still lives in Postgres.
"""

import threading
from collections import deque
from typing import Deque, Dict, List

_MAX_POINTS = 80
_MAX_VEHICLES = 40
_lock = threading.Lock()
_tracks: Dict[str, Deque[dict]] = {}


def record(vehicle_id: str, lat: float, lon: float, timestamp_ms: int, in_zone: bool) -> None:
    point = {
        "lat": lat,
        "lon": lon,
        "timestamp": timestamp_ms,
        "inZone": in_zone,
    }
    with _lock:
        trail = _tracks.get(vehicle_id)
        if trail is None:
            if len(_tracks) >= _MAX_VEHICLES:
                oldest = next(iter(_tracks))
                _tracks.pop(oldest, None)
            trail = deque(maxlen=_MAX_POINTS)
            _tracks[vehicle_id] = trail
        trail.append(point)


def snapshot() -> List[dict]:
    with _lock:
        return [
            {"vehicleId": vehicle_id, "points": list(points)}
            for vehicle_id, points in _tracks.items()
        ]
