"""Connection settings shared by the local Compose stack and the hosted demo.

PLAINTEXT Kafka, a Redis host and port, and discrete Postgres fields stay the
defaults, so `docker compose up` does not need new variables. Hosted brokers
opt in with KAFKA_SECURITY_PROTOCOL, REDIS_URL, and DATABASE_URL.
"""

import os
from typing import Mapping, Optional
from urllib.parse import urlsplit, urlunsplit


APPLICATION_TOPICS = (
    ("smarttoll.gps.raw.v1", 2),
    ("smarttoll.toll.events.v1", 2),
    ("smarttoll.payment.events.v1", 2),
    ("smarttoll.billing.dlq.v1", 2),
    ("smarttoll.processor.errors.v1", 2),
)
TOPIC_REPLICATION_FACTOR = 1

_BROKER_SCHEMES = (
    "SASL_SSL://",
    "SASL_PLAINTEXT://",
    "SSL://",
    "PLAINTEXT://",
    "kafka+ssl://",
    "kafka://",
)


def normalize_broker(broker: str) -> str:
    """Return host:port pairs. Aiven sometimes prefixes a scheme."""
    text = (broker or "").strip()
    lowered = text.lower()
    for scheme in _BROKER_SCHEMES:
        if lowered.startswith(scheme.lower()):
            text = text[len(scheme):]
            break
    return text.strip()


def _mapping(env: Optional[Mapping[str, str]]) -> Mapping[str, str]:
    if env is None:
        return os.environ
    return env


def _secret_dir(env: Mapping[str, str]) -> str:
    return (env.get("SMARTTOLL_SECRET_DIR") or "/tmp").strip() or "/tmp"


def materialize_pem(pem_text: Optional[str], file_path: Optional[str], filename: str, env: Mapping[str, str]) -> Optional[str]:
    """Return a filesystem path for a PEM supplied as a file or as text."""
    path = (file_path or "").strip()
    if path:
        if os.path.isfile(path):
            return path
        if not (pem_text or "").strip():
            raise ValueError(f"{filename} was set to {path}, but that file does not exist")
    text = (pem_text or "").strip()
    if not text:
        return None
    text = text.replace("\\n", "\n")
    if "BEGIN" not in text:
        raise ValueError(f"{filename} does not look like a PEM document")
    if not text.endswith("\n"):
        text += "\n"
    directory = _secret_dir(env)
    os.makedirs(directory, exist_ok=True)
    dest = os.path.join(directory, filename)
    descriptor = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(text)
    return dest


def kafka_security_kwargs(env: Optional[Mapping[str, str]] = None) -> dict:
    """kwargs for kafka-python clients. Empty for the local PLAINTEXT broker."""
    env = _mapping(env)
    protocol = (env.get("KAFKA_SECURITY_PROTOCOL") or "PLAINTEXT").strip().upper()
    if protocol == "PLAINTEXT":
        return {}
    if protocol not in {"SASL_SSL", "SSL", "SASL_PLAINTEXT"}:
        raise ValueError(
            "KAFKA_SECURITY_PROTOCOL must be PLAINTEXT, SASL_SSL, SSL, or SASL_PLAINTEXT"
        )
    kwargs = {"security_protocol": protocol}
    if protocol in {"SASL_SSL", "SSL"}:
        ca_file = materialize_pem(
            env.get("KAFKA_SSL_CA_PEM"),
            env.get("KAFKA_SSL_CA_FILE"),
            "kafka-ca.pem",
            env,
        )
        if not ca_file:
            raise ValueError("KAFKA_SSL_CA_PEM or KAFKA_SSL_CA_FILE is required for " + protocol)
        kwargs["ssl_cafile"] = ca_file
        check = (env.get("KAFKA_SSL_CHECK_HOSTNAME") or "true").strip().lower()
        kwargs["ssl_check_hostname"] = check not in {"0", "false", "no"}
    if protocol == "SSL":
        cert = materialize_pem(env.get("KAFKA_SSL_CERT_PEM"), env.get("KAFKA_SSL_CERT_FILE"), "kafka-cert.pem", env)
        key = materialize_pem(env.get("KAFKA_SSL_KEY_PEM"), env.get("KAFKA_SSL_KEY_FILE"), "kafka-key.pem", env)
        if cert:
            kwargs["ssl_certfile"] = cert
        if key:
            kwargs["ssl_keyfile"] = key
    if protocol.startswith("SASL"):
        username = (env.get("KAFKA_SASL_USERNAME") or "").strip()
        password = env.get("KAFKA_SASL_PASSWORD") or ""
        if not username or not password:
            raise ValueError("KAFKA_SASL_USERNAME and KAFKA_SASL_PASSWORD are required for " + protocol)
        kwargs["sasl_mechanism"] = (env.get("KAFKA_SASL_MECHANISM") or "SCRAM-SHA-256").strip()
        kwargs["sasl_plain_username"] = username
        kwargs["sasl_plain_password"] = password
    return kwargs


def redis_client_kwargs(env: Optional[Mapping[str, str]] = None, settings=None) -> dict:
    """Arguments for redis.Redis. A rediss:// URL turns TLS on."""
    env = _mapping(env)
    url = (env.get("REDIS_URL") or "").strip()
    if not url and settings is not None:
        url = str(getattr(settings, "REDIS_URL", "") or "").strip()
    common = {
        "decode_responses": True,
        "socket_connect_timeout": 5,
        "socket_keepalive": True,
        "health_check_interval": 30,
    }
    if url:
        if not url.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL must start with redis:// or rediss://")
        return {"from_url": url, **common}
    if settings is not None:
        return {
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT,
            "db": settings.REDIS_DB,
            **common,
        }
    return {
        "host": env.get("REDIS_HOST") or "redis",
        "port": int(env.get("REDIS_PORT") or "6379"),
        "db": int(env.get("REDIS_DB") or "0"),
        **common,
    }


def redis_target_for_log(params: Mapping) -> str:
    """Host and scheme only, so a password in the URL is not logged."""
    url = params.get("from_url")
    if url:
        parts = urlsplit(url)
        port = f":{parts.port}" if parts.port else ""
        return f"{parts.scheme}://{parts.hostname}{port}"
    return f"{params.get('host')}:{params.get('port')}/{params.get('db')}"


def to_libpq_dsn(url: str) -> str:
    """Accept postgres:// and SQLAlchemy driver URLs."""
    text = (url or "").strip()
    for prefix in ("postgresql+psycopg2://", "postgresql+asyncpg://", "postgres://"):
        if text.startswith(prefix):
            return "postgresql://" + text[len(prefix):]
    return text


def redact_database_url(url: str) -> str:
    parts = urlsplit(url)
    if not parts.password:
        return url
    netloc = parts.netloc.replace(parts.password, "********")
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def postgres_connect_kwargs(env: Optional[Mapping[str, str]] = None, settings=None) -> dict:
    """psycopg2 keyword arguments. DATABASE_URL wins over host, user, and port."""
    env = _mapping(env)
    url = (env.get("DATABASE_URL") or "").strip()
    if not url and settings is not None:
        url = str(getattr(settings, "DATABASE_URL", "") or "").strip()
    if settings is not None and getattr(settings, "POSTGRES_CONNECT_TIMEOUT", None):
        timeout = settings.POSTGRES_CONNECT_TIMEOUT
    else:
        timeout = int(env.get("POSTGRES_CONNECT_TIMEOUT") or "10")
    if url:
        return {"dsn": to_libpq_dsn(url), "connect_timeout": timeout}
    if settings is not None:
        return {
            "user": settings.POSTGRES_USER,
            "password": settings.POSTGRES_PASSWORD,
            "host": settings.POSTGRES_HOST,
            "port": settings.POSTGRES_PORT,
            "database": settings.POSTGRES_DB,
            "connect_timeout": timeout,
        }
    return {
        "user": env.get("POSTGRES_USER") or "smarttoll_user",
        "password": env.get("POSTGRES_PASSWORD") or "",
        "host": env.get("POSTGRES_HOST") or "postgres",
        "port": int(env.get("POSTGRES_PORT") or "5432"),
        "database": env.get("POSTGRES_DB") or "smarttoll_dev",
        "connect_timeout": timeout,
    }
