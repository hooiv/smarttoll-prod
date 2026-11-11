"""Drive N vehicles through the Kherki Daula plaza and report how many charges landed.

Usage (stack already up):
    python scripts/load_trips.py --vehicles 20
"""

import argparse
import json
import time
import urllib.request

from kafka import KafkaProducer

BROKER = "127.0.0.1:9092"
TOPIC = "smarttoll.gps.raw.v1"
API = "http://127.0.0.1:8001/api/v1/transactions"
API_KEY = "supersecretapikey123"


def send_trip(producer: KafkaProducer, vehicle_id: str) -> None:
    now = int(time.time() * 1000)
    points = [
        (28.40004, 76.98636, now),
        (28.39543, 76.98205, now + 2000),
        (28.36174, 76.93575, now + 4000),
    ]
    for lat, lon, ts in points:
        payload = {
            "deviceId": f"OBU_{vehicle_id}",
            "vehicleId": vehicle_id,
            "traceId": f"load-{vehicle_id}-{ts}",
            "timestamp": ts,
            "latitude": lat,
            "longitude": lon,
            "speedKmph": 50,
        }
        producer.send(TOPIC, key=vehicle_id.encode(), value=payload)
        time.sleep(0.05)
    producer.flush()


def count_for(prefix: str) -> tuple[int, int]:
    request = urllib.request.Request(f"{API}?page_size=100", headers={"X-API-KEY": API_KEY})
    with urllib.request.urlopen(request, timeout=10) as response:
        body = json.loads(response.read().decode())
    matched = sum(1 for item in body["items"] if str(item["vehicle_id"]).startswith(prefix))
    return matched, int(body["total"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vehicles", type=int, default=20)
    parser.add_argument("--prefix", default="DL01AB")
    args = parser.parse_args()
    producer = KafkaProducer(
        bootstrap_servers=BROKER,
        api_version=(3, 3, 1),
        value_serializer=lambda value: json.dumps(value).encode(),
        acks=1,
    )
    started = time.perf_counter()
    for index in range(args.vehicles):
        send_trip(producer, f"{args.prefix}{index:03d}")
    producer.close()
    sent_at = time.perf_counter()

    matched = 0
    deadline = time.time() + 60
    while time.time() < deadline:
        matched, _total = count_for(args.prefix)
        if matched >= args.vehicles:
            break
        time.sleep(1)
    elapsed = time.perf_counter() - started
    print(
        json.dumps(
            {
                "vehicles": args.vehicles,
                "billed": matched,
                "publish_seconds": round(sent_at - started, 2),
                "e2e_seconds": round(elapsed, 2),
            },
            indent=2,
        )
    )
    if matched < args.vehicles:
        raise SystemExit(f"only {matched} of {args.vehicles} trips were billed within 60s")


if __name__ == "__main__":
    main()
