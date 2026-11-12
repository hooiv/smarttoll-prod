"""scripts/load_trips.py must take the API key from the environment."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "load_trips.py"


def _load():
    spec = importlib.util.spec_from_file_location("load_trips_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_does_not_embed_an_api_key():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "supersecretapikey123" not in text
    assert "SMARTTOLL_API_KEY" in text


def test_missing_api_key_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("SMARTTOLL_API_KEY", raising=False)
    module = _load()
    with pytest.raises(SystemExit, match="SMARTTOLL_API_KEY"):
        module.require_api_key()


def test_api_key_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("SMARTTOLL_API_KEY", "from-the-env")
    module = _load()
    assert module.require_api_key() == "from-the-env"
