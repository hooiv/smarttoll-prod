"""Topic creation stays inside the Aiven free-tier budget."""

import importlib.util
from pathlib import Path

from kafka.errors import TopicAlreadyExistsError

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("create_topics", ROOT / "scripts" / "create_topics.py")
create_topics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(create_topics)


class _Admin:
    def __init__(self, existing=()):
        self.created = []
        self.existing = set(existing)

    def create_topics(self, new_topics, validate_only=False):
        topic = new_topics[0]
        if topic.name in self.existing:
            raise TopicAlreadyExistsError(f"{topic.name} already exists")
        self.created.append((topic.name, topic.num_partitions, topic.replication_factor))


def test_ensure_topics_creates_five_with_two_partitions_and_replication_one():
    admin = _Admin()
    notes = create_topics.ensure_topics(admin)
    assert len(admin.created) == 5
    assert {item[1] for item in admin.created} == {2}
    assert {item[2] for item in admin.created} == {1}
    assert all(note.startswith("created ") for note in notes)


def test_existing_topic_is_not_a_failure():
    admin = _Admin(existing={"smarttoll.gps.raw.v1"})
    notes = create_topics.ensure_topics(admin)
    assert any(note == "exists smarttoll.gps.raw.v1" for note in notes)
    assert len(admin.created) == 4


def test_admin_kwargs_include_sasl_ssl(tmp_path):
    pem = "-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----\n"
    kwargs = create_topics.admin_client_kwargs({
        "KAFKA_BROKER": "SASL_SSL://kafka-demo.aivencloud.com:17000",
        "KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
        "KAFKA_SASL_USERNAME": "avnadmin",
        "KAFKA_SASL_PASSWORD": "pw",
        "KAFKA_SSL_CA_PEM": pem,
        "SMARTTOLL_SECRET_DIR": str(tmp_path),
    })
    assert kwargs["bootstrap_servers"] == "kafka-demo.aivencloud.com:17000"
    assert kwargs["security_protocol"] == "SASL_SSL"
    assert kwargs["sasl_mechanism"] == "SCRAM-SHA-256"
