"""Code/config version contract and the startup compatibility check."""

from __future__ import annotations

CODE_VERSION = "1.00"


class VersionMismatchError(RuntimeError):
    """Raised when a config file's version is incompatible with the code."""


def parse_version(value: str) -> tuple[int, int]:
    """Parse a 'major.minor' version string into a comparable tuple."""
    try:
        major, minor = value.split(".")
        return int(major), int(minor)
    except (ValueError, AttributeError) as exc:
        raise VersionMismatchError(f"Malformed version string: {value!r}") from exc


def check_compatibility(config_version: str, *, source: str = "config") -> None:
    """Fail fast when a config file's major version differs from the code's.

    Minor-version drift is tolerated (backwards-compatible additions);
    a major bump means the schema changed and the code must not proceed.
    """
    code_major, _ = parse_version(CODE_VERSION)
    cfg_major, _ = parse_version(config_version)
    if cfg_major != code_major:
        raise VersionMismatchError(
            f"{source} version {config_version} is incompatible with code version {CODE_VERSION}"
        )
