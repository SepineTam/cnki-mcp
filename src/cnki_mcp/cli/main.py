#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : cli/main.py

"""Command-line interface for cnki-mcp."""

import argparse
import json
import sys
from typing import Any

from ..core.client import CnkiClient
from ..core.exceptions import CnkiMcpError


def _format_output(data: Any, output_format: str) -> str:
    """Format command output for stdout.

    Args:
        data: Data to format.
        output_format: Either "json" or "text".

    Returns:
        Formatted string.

    Raises:
        ValueError: If the output format is not supported.
    """
    if output_format == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)
    if output_format == "text":
        return str(data)
    raise ValueError(f"unsupported output format: {output_format!r}")


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    # Options with defaults for the top-level parser.
    global_parser = argparse.ArgumentParser(add_help=False)
    global_parser.add_argument(
        "--profile",
        "-p",
        default=None,
        help="Profile name",
    )
    global_parser.add_argument(
        "--output",
        "-o",
        choices=["json", "text"],
        default="json",
        help="Output format",
    )

    # Same options but suppressed defaults so subparsers do not overwrite
    # values already parsed by the top-level parser when options appear
    # before the subcommand.
    sub_parser = argparse.ArgumentParser(add_help=False)
    sub_parser.add_argument(
        "--profile",
        "-p",
        default=argparse.SUPPRESS,
        help="Profile name",
    )
    sub_parser.add_argument(
        "--output",
        "-o",
        choices=["json", "text"],
        default=argparse.SUPPRESS,
        help="Output format",
    )

    parser = argparse.ArgumentParser(
        prog="cnki-mcp-cli",
        description="CNKI MCP command-line interface",
        parents=[global_parser],
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser(
        "search",
        help="Search CNKI",
        parents=[sub_parser],
    )
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum results",
    )

    metadata_parser = subparsers.add_parser(
        "metadata",
        help="Fetch article metadata",
        parents=[sub_parser],
    )
    metadata_parser.add_argument("article_id", help="Article identifier")

    subparsers.add_parser(
        "login",
        help="Log in to CNKI",
        parents=[sub_parser],
    )
    subparsers.add_parser(
        "logout",
        help="Log out from CNKI",
        parents=[sub_parser],
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the cnki-mcp CLI.

    Args:
        argv: Optional command-line arguments.

    Returns:
        Exit code.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    client = CnkiClient(profile=args.profile)

    try:
        if args.command == "search":
            results = client.search(args.query, limit=args.limit)
            data = [r.__dict__ for r in results]
        elif args.command == "metadata":
            article = client.get_metadata(args.article_id)
            data = article.__dict__
        elif args.command == "login":
            result = client.login()
            data = {
                "success": result.success,
                "message": result.message,
                "profile": result.auth_state.profile,
            }
        elif args.command == "logout":
            client.logout()
            data = {
                "success": True,
                "message": "logged out",
                "profile": client.current_profile,
            }
        else:
            parser.print_help()
            return 1
    except CnkiMcpError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(_format_output(data, args.output))
    return 0


__all__ = ["_format_output", "main"]
