"""Config manager: loads versioned JSON config files and exposes typed getters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentscribe import constants
from agentscribe.shared.version import check_compatibility


class ConfigError(RuntimeError):
    """Raised when a config file is missing or malformed."""


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Malformed JSON in {path}: {exc}") from exc


class Config:
    """Typed access to setup / rate-limit / logging / price config (all versioned)."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self._dir = config_dir or constants.CONFIG_DIR
        self._setup = _load_json(self._dir / constants.SETUP_CONFIG)
        self._rate_limits = _load_json(self._dir / constants.RATE_LIMITS_CONFIG)["rate_limits"]
        self._logging = _load_json(self._dir / constants.LOGGING_CONFIG)
        self._prices = _load_json(self._dir / constants.MODEL_PRICES_CONFIG)
        for cfg, name in (
            (self._setup, constants.SETUP_CONFIG),
            (self._rate_limits, constants.RATE_LIMITS_CONFIG),
            (self._logging, constants.LOGGING_CONFIG),
            (self._prices, constants.MODEL_PRICES_CONFIG),
        ):
            check_compatibility(str(cfg.get("version", "")), source=name)

    # -- setup.json ---------------------------------------------------------
    @property
    def language(self) -> str:
        return str(self._setup["language"])

    @property
    def bidi_language(self) -> str:
        return str(self._setup["bidi_chapter_language"])

    @property
    def target_pages(self) -> int:
        return int(self._setup["target_pages"])

    @property
    def compiler(self) -> constants.Compiler:
        return constants.Compiler(self._setup["compiler"])

    @property
    def compile_passes(self) -> int:
        return int(self._setup["compile_passes"])

    @property
    def bib_backend(self) -> constants.BibBackend:
        return constants.BibBackend(self._setup["bib_backend"])

    @property
    def document_class(self) -> str:
        return str(self._setup["document_class"])

    @property
    def worker_model(self) -> str:
        return str(self._setup["worker_model"])

    @property
    def engineer_model(self) -> str:
        return str(self._setup["engineer_model"])

    @property
    def human_in_the_loop(self) -> bool:
        return bool(self._setup["human_in_the_loop"])

    @property
    def results_dir(self) -> Path:
        return constants.PROJECT_ROOT / str(self._setup["results_dir"])

    @property
    def cover(self) -> dict[str, str]:
        return dict(self._setup["cover"])

    # -- rate_limits.json ---------------------------------------------------
    def service_limits(self, service: str) -> dict[str, int]:
        services = self._rate_limits["services"]
        return dict(services.get(service, services["default"]))

    @property
    def queue_config(self) -> dict[str, Any]:
        return dict(self._rate_limits["queue"])

    # -- logging_config.json ------------------------------------------------
    @property
    def log_level(self) -> str:
        return str(self._logging["level"])

    @property
    def redact_keys(self) -> list[str]:
        return list(self._logging["redact_keys"])

    # -- model_prices.json --------------------------------------------------
    def model_price(self, model: str) -> dict[str, float]:
        prices = self._prices["prices_per_million_tokens_usd"]
        if model not in prices:
            raise ConfigError(f"Model {model!r} missing from {constants.MODEL_PRICES_CONFIG}")
        return {k: float(v) for k, v in prices[model].items()}

    def validate_models(self) -> None:
        """Fail fast if configured models have no price entry (AI_STACK risk note)."""
        for model in (self.worker_model, self.engineer_model):
            self.model_price(model)
