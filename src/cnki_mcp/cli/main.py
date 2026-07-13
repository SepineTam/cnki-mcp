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
from dataclasses import asdict
from typing import Any

from ..core.client import CnkiClient
from ..core.exceptions import CnkiMcpError
from ..core.tools.professional_search import PROFESSIONAL_SEARCH_GUIDE


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
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=PROFESSIONAL_SEARCH_GUIDE,
    )
    search_parser.add_argument(
        "query",
        help="CNKI professional expression, or a plain article title",
    )
    search_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum results",
    )
    search_parser.add_argument(
        "--sort-by",
        choices=["relevance", "date", "citation", "comprehensive"],
        default=None,
        help="Sort results by relevance, date, citation, or comprehensive score",
    )
    search_parser.add_argument(
        "--year-from",
        type=int,
        default=None,
        help="Start publication year",
    )
    search_parser.add_argument(
        "--year-to",
        type=int,
        default=None,
        help="End publication year",
    )
    search_parser.add_argument(
        "--journal",
        default=None,
        help="Journal or source title",
    )
    search_parser.add_argument(
        "--document-type",
        default=None,
        help="Resource type such as journal, conference, dissertation, or newspaper",
    )
    search_parser.add_argument(
        "--source-type",
        action="append",
        dest="source_types",
        default=None,
        help="Source category such as CSSCI, SCI, EI, CSCD, AMI, or 北大核心",
    )
    search_parser.add_argument(
        "--author",
        default=None,
        help="Author filter",
    )
    search_parser.add_argument(
        "--institution",
        default=None,
        help="Author institution filter",
    )

    metadata_parser = subparsers.add_parser(
        "metadata",
        help="Fetch article metadata",
        parents=[sub_parser],
    )
    metadata_parser.add_argument("article_id", help="Article identifier")

    lookup_parser = subparsers.add_parser(
        "lookup-metadata",
        help="Resolve metadata from known citation fields",
        parents=[sub_parser],
    )
    lookup_parser.add_argument("title", help="Article title")
    lookup_parser.add_argument(
        "--author",
        action="append",
        dest="authors",
        default=None,
        help="Article author; repeat for multiple authors",
    )
    lookup_parser.add_argument("--year", type=int, default=None)
    lookup_parser.add_argument(
        "--source",
        "--journal",
        dest="source",
        default=None,
        help="Article source or journal title",
    )
    lookup_parser.add_argument("--document-type", default=None)
    lookup_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum candidates",
    )

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
            search_kwargs: dict[str, Any] = {"limit": args.limit}
            if args.sort_by:
                search_kwargs["sort_by"] = args.sort_by
            for key in [
                "year_from",
                "year_to",
                "journal",
                "document_type",
                "source_types",
                "author",
                "institution",
            ]:
                value = getattr(args, key)
                if value:
                    search_kwargs[key] = value
            results = client.search(args.query, **search_kwargs)
            data = [result.to_public_dict() for result in results]
        elif args.command == "metadata":
            article = client.get_metadata(args.article_id)
            data = article.__dict__
        elif args.command == "lookup-metadata":
            result = client.lookup_metadata(
                args.title,
                authors=args.authors,
                year=args.year,
                source=args.source,
                document_type=args.document_type,
                limit=args.limit,
            )
            data = asdict(result)
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
