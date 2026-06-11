"""Thin CLI wrapper around the SDK. No business logic here (PLAN.md section 5)."""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentscribe",
        description="Generate a typeset PDF article on any topic via a CrewAI pipeline.",
    )
    parser.add_argument("--topic", required=True, help="Topic to write the document about")
    parser.add_argument("--language", default=None, help="Main document language (default: config)")
    parser.add_argument(
        "--target-pages", type=int, default=None, help="Approximate page target (default: config)"
    )
    parser.add_argument(
        "--markdown-only", action="store_true", help="Stop after the Markdown draft (FR-12)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.topic.strip():
        print("error: --topic must be a non-empty string", file=sys.stderr)
        return 2
    from agentscribe.sdk.sdk import AgentScribeSDK

    sdk = AgentScribeSDK.from_default_config()
    result = sdk.generate_document(
        args.topic,
        language=args.language,
        target_pages=args.target_pages,
        markdown_only=args.markdown_only,
    )
    print(result.summary())
    return 0 if result.status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
