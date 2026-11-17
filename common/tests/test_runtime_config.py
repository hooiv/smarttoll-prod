"""SASL/SSL Kafka settings and TLS Redis URLs."""

from pathlib import Path

import pytest

from common.runtime_config import (
    APPLICATION_TOPICS,
    kafka_security_kwargs,
    postgres_connect_kwargs,
    redis_client_kwargs,
    redis_target_for_log,
    to_libpq_dsn,
)

PEM = "-----BEGIN CERTIFICATE-----\nMIIBtest\n-----END CERTIFICATE-----\n"
ROOT = Path(__file__).resolve().parents[2]


def test_plaintext_kafka_adds_no_security_kwargs():
    assert kafka_security_kwargs({}) == {}


def test_sasl_ssl_scram_writes_the_ca(tmp_path):
    kwargs = kafka_security_kwargs({
        "KAFKA_SECURITY_PROTOCOL": "sasl_ssl",
        "KAFKA_SASL_USERNAME": "avnadmin",
        "KAFKA_SASL_PASSWORD": "s3cret",
        "KAFKA_SSL_CA_PEM": PEM.replace("\n", "\\n"),
        "SMARTTOLL_SECRET_DIR": str(tmp_path),
    })
    assert kwargs["security_protocol"] == "SASL_SSL"
    assert kwargs["sasl_mechanism"] == "SCRAM-SHA-256"
    assert kwargs["sasl_plain_username"] == "avnadmin"
    assert kwargs["sasl_plain_password"] == "s3cret"
    assert kwargs["ssl_check_hostname"] is True
    ca = Path(kwargs["ssl_cafile"])
    assert ca.read_text(encoding="utf-8").startswith("-----BEGIN CERTIFICATE-----")
    assert oct(ca.stat().st_mode & 0o777) == "0o600"


def test_sasl_mechanism_can_be_plain(tmp_path):
    kwargs = kafka_security_kwargs({
        "KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
        "KAFKA_SASL_MECHANISM": "PLAIN",
        "KAFKA_SASL_USERNAME": "user",
        "KAFKA_SASL_PASSWORD": "pw",
        "KAFKA_SSL_CA_PEM": PEM,
        "SMARTTOLL_SECRET_DIR": str(tmp_path),
    })
    assert kwargs["sasl_mechanism"] == "PLAIN"
    with pytest.raises(ValueError, match="does not exist"):
        kafka_security_kwargs({
            "KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
            "KAFKA_SASL_MECHANISM": "PLAIN",
            "KAFKA_SASL_USERNAME": "user",
            "KAFKA_SASL_PASSWORD": "pw",
            "KAFKA_SSL_CA_FILE": str(tmp_path / "missing.pem"),
        })


def test_sasl_ssl_requires_credentials_and_ca():
    with pytest.raises(ValueError, match="KAFKA_SASL_USERNAME"):
        kafka_security_kwargs({
            "KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
            "KAFKA_SSL_CA_PEM": PEM,
        })
    with pytest.raises(ValueError, match="KAFKA_SSL_CA"):
        kafka_security_kwargs({
            "KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
            "KAFKA_SASL_USERNAME": "user",
            "KAFKA_SASL_PASSWORD": "pw",
        })


def test_ssl_client_certificate(tmp_path):
    kwargs = kafka_security_kwargs({
        "KAFKA_SECURITY_PROTOCOL": "SSL",
        "KAFKA_SSL_CA_PEM": PEM,
        "KAFKA_SSL_CERT_PEM": PEM.replace("CERTIFICATE", "CERTIFICATE"),
        "KAFKA_SSL_KEY_PEM": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----\n",
        "KAFKA_SSL_CHECK_HOSTNAME": "false",
        "SMARTTOLL_SECRET_DIR": str(tmp_path),
    })
    assert kwargs["security_protocol"] == "SSL"
    assert kwargs["ssl_check_hostname"] is False
    assert Path(kwargs["ssl_certfile"]).is_file()
    assert Path(kwargs["ssl_keyfile"]).is_file()
    assert "sasl_plain_password" not in kwargs


def test_rediss_url_is_the_tls_connection():
    params = redis_client_kwargs({
        "REDIS_URL": "rediss://default:secret@valkey.example.com:25061/0",
        "REDIS_HOST": "redis",
    })
    assert params["from_url"].startswith("rediss://")
    assert redis_target_for_log(params) == "rediss://valkey.example.com:25061"
    assert "secret" not in redis_target_for_log(params)


def test_redis_url_rejects_a_non_redis_scheme():
    with pytest.raises(ValueError, match="rediss://"):
        redis_client_kwargs({"REDIS_URL": "http://example.com"})


def test_local_redis_stays_on_host_and_port():
    params = redis_client_kwargs({})
    assert params["host"] == "redis"
    assert params["port"] == 6379
    assert "from_url" not in params


def test_local_postgres_uses_host_fields_when_database_url_is_unset():
    class Settings:
        DATABASE_URL = None
        POSTGRES_USER = "smarttoll_user"
        POSTGRES_PASSWORD = "local"
        POSTGRES_HOST = "postgres"
        POSTGRES_PORT = 5432
        POSTGRES_DB = "smarttoll_dev"
        POSTGRES_CONNECT_TIMEOUT = 10

    kwargs = postgres_connect_kwargs({}, settings=Settings())
    assert "dsn" not in kwargs
    assert kwargs["host"] == "postgres"
    assert kwargs["database"] == "smarttoll_dev"


def test_database_url_becomes_a_libpq_dsn():
    kwargs = postgres_connect_kwargs({
        "DATABASE_URL": "postgresql+psycopg2://avnadmin:pw@pg.aivencloud.com:12345/defaultdb?sslmode=require",
    })
    assert kwargs["dsn"].startswith("postgresql://avnadmin:pw@pg.aivencloud.com:12345/defaultdb")
    assert "sslmode=require" in kwargs["dsn"]
    assert to_libpq_dsn("postgres://u:p@h:1/db") == "postgresql://u:p@h:1/db"


def test_hosted_topic_budget_is_five_topics_of_two_partitions():
    names = [name for name, _parts in APPLICATION_TOPICS]
    assert names == [
        "smarttoll.gps.raw.v1",
        "smarttoll.toll.events.v1",
        "smarttoll.payment.events.v1",
        "smarttoll.billing.dlq.v1",
        "smarttoll.processor.errors.v1",
    ]
    assert {parts for _name, parts in APPLICATION_TOPICS} == {2}
    processor = (ROOT / "toll_processor" / "app" / "config.py").read_text(encoding="utf-8")
    billing = (ROOT / "billing_service" / "app" / "config.py").read_text(encoding="utf-8")
    assert "smarttoll.gps.raw.v1" in processor
    assert "smarttoll.processor.errors.v1" in processor
    assert "smarttoll.toll.events.v1" in billing
    assert "smarttoll.billing.dlq.v1" in billing
    assert "smarttoll.payment.events.v1" in billing


def test_deploy_doc_names_the_topics_and_secrets():
    text = (ROOT / "DEPLOY.md").read_text(encoding="utf-8")
    for name, _parts in APPLICATION_TOPICS:
        assert name in text
    for token in (
        "HF_BACKEND_URL",
        "SERVICE_API_KEY",
        "REDIS_URL",
        "rediss://",
        "DATABASE_URL",
        "KAFKA_SSL_CA_PEM",
        "SCRAM-SHA-256",
        "300 seconds",
        "PostGIS",
    ):
        assert token in text


def test_service_copies_match_the_shared_module():
    source = (ROOT / "common" / "runtime_config.py").read_bytes()
    for copy in (
        ROOT / "billing_service" / "app" / "runtime_config.py",
        ROOT / "toll_processor" / "app" / "runtime_config.py",
        ROOT / "obu_simulator" / "runtime_config.py",
    ):
        assert copy.read_bytes() == source
