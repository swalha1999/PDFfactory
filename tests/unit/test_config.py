"""Tests for shared/config.py - typed getters and version validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentscribe import constants
from agentscribe.shared.config import Config, ConfigError
from agentscribe.shared.version import VersionMismatchError


@pytest.fixture
def config() -> Config:
    return Config()  # real repo config/ - it must always be loadable


def test_setup_getters(config: Config) -> None:
    assert config.language == "en"
    assert config.bidi_language == "he"
    assert config.target_pages == 15
    assert config.compiler == constants.Compiler.LUALATEX
    assert config.compile_passes == 4
    assert config.document_class == "article"
    assert config.human_in_the_loop is False
    assert "author" in config.cover


def test_rate_limit_getters(config: Config) -> None:
    llm = config.service_limits("llm")
    assert llm["requests_per_minute"] == 20
    assert config.service_limits("unknown-service") == config.service_limits("default")
    assert config.queue_config["max_depth"] == 100


def test_logging_and_prices(config: Config) -> None:
    assert config.log_level == "INFO"
    assert "api_key" in config.redact_keys
    price = config.model_price(config.worker_model)
    assert price["input"] > 0 and price["output"] > 0
    config.validate_models()  # must not raise


def test_unknown_model_price_raises(config: Config) -> None:
    with pytest.raises(ConfigError, match="no-such-model"):
        config.model_price("no-such-model")


def test_missing_config_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        Config(config_dir=tmp_path)


def test_malformed_json_raises(tmp_path: Path) -> None:
    (tmp_path / constants.SETUP_CONFIG).write_text("{not json")
    with pytest.raises(ConfigError, match="Malformed"):
        Config(config_dir=tmp_path)


def test_version_mismatch_raises(tmp_path: Path) -> None:
    src = constants.CONFIG_DIR
    for name in (
        constants.SETUP_CONFIG,
        constants.RATE_LIMITS_CONFIG,
        constants.LOGGING_CONFIG,
        constants.MODEL_PRICES_CONFIG,
    ):
        (tmp_path / name).write_text((src / name).read_text())
    bad = json.loads((src / constants.SETUP_CONFIG).read_text())
    bad["version"] = "9.00"
    (tmp_path / constants.SETUP_CONFIG).write_text(json.dumps(bad))
    with pytest.raises(VersionMismatchError):
        Config(config_dir=tmp_path)
