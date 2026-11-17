"""Create the five SmartToll topics on a broker that does not auto-create them.

Aiven's free Kafka plan disables auto-creation and allows five topics, two
partitions each. Run this once after the service is Running, from the repo
root, with the same KAFKA_* variables the Space will use:

    python scripts/create_topics.py

Existing topics are left alone. Replication is 1 because the free plan is a
single broker. Do not also create a schema-registry topic; that would be a
sixth topic and the plan will reject it.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kafka.admin import KafkaAdminClient, NewTopic  # noqa: E402
from kafka.errors import KafkaError, TopicAlreadyExistsError  # noqa: E402

from common.runtime_config import (  # noqa: E402
    APPLICATION_TOPICS,
    TOPIC_REPLICATION_FACTOR,
    kafka_security_kwargs,
    normalize_broker,
)


def _already_exists(exc: BaseException) -> bool:
    if isinstance(exc, TopicAlreadyExistsError):
        return True
    text = f"{type(exc).__name__} {exc}".lower()
    return "already exists" in text or "topicexists" in text


def admin_client_kwargs(env=None) -> dict:
    import os
    env = env if env is not None else os.environ
    broker = normalize_broker(env.get("KAFKA_BROKER") or "")
    if not broker:
        raise SystemExit("KAFKA_BROKER is not set. Use the Aiven bootstrap host:port.")
    return {
        "bootstrap_servers": broker,
        "client_id": "smarttoll-create-topics",
        "api_version": (3, 3, 1),
        **kafka_security_kwargs(env),
    }


def ensure_topics(admin) -> list[str]:
    notes = []
    for name, partitions in APPLICATION_TOPICS:
        topic = NewTopic(
            name=name,
            num_partitions=partitions,
            replication_factor=TOPIC_REPLICATION_FACTOR,
        )
        try:
            admin.create_topics(new_topics=[topic], validate_only=False)
            notes.append(
                f"created {name} partitions={partitions} replication={TOPIC_REPLICATION_FACTOR}"
            )
        except (TopicAlreadyExistsError, KafkaError) as exc:
            if _already_exists(exc):
                notes.append(f"exists {name}")
            else:
                raise
    return notes


def main() -> None:
    kwargs = admin_client_kwargs()
    admin = KafkaAdminClient(**kwargs)
    try:
        for line in ensure_topics(admin):
            print(line)
    finally:
        admin.close()
    print(f"{len(APPLICATION_TOPICS)} topics are the whole free-tier budget.")


if __name__ == "__main__":
    main()
