#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : cli/main.py

"""Unified command-line interface for cnki-mcp."""

import argparse
import json
import sys
from dataclasses import asdict
from importlib.metadata import PackageNotFoundError, version
from typing import Any
from urllib.parse import urlparse

from ..core.client import CnkiClient
from ..core.exceptions import CnkiMcpError
from ..core.tools.professional_search import PROFESSIONAL_SEARCH_GUIDE
from ..server.cnki_mcp_server import create_mcp_server

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7788
TRANSPORT_MAP = {
    "http": "streamable-http",
    "sse": "sse",
    "stdio": "stdio",
}


def _package_version() -> str:
    """Return the installed package version with a source-tree fallback."""
    try:
        return version("cnki-mcp")
    except PackageNotFoundError:
        return "0.1.0"


def _format_output(data: Any, output_format: str) -> str:
    """Format command output for stdout."""
    if output_format == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)
    if output_format == "text":
        return str(data)
    raise ValueError(f"unsupported output format: {output_format!r}")


def _add_profile_option(parser: argparse.ArgumentParser) -> None:
    """Add the shared profile option to a command parser."""
    parser.add_argument("--profile", "-p", default=None, help="Profile name")


def _add_output_option(parser: argparse.ArgumentParser) -> None:
    """Add the shared output option to a tool parser."""
    parser.add_argument(
        "--output",
        "-o",
        choices=["json", "text"],
        default="json",
        help="Output format",
    )


def _add_search_filters(parser: argparse.ArgumentParser) -> None:
    """Add shared search filters and result options."""
    parser.add_argument("--limit", type=int, default=10, help="Maximum results")
    parser.add_argument(
        "--sort-by",
        choices=["relevance", "date", "citation", "comprehensive"],
        default=None,
        help="Sort by relevance, date, citation, or comprehensive score",
    )
    parser.add_argument("--year-from", type=int, default=None)
    parser.add_argument("--year-to", type=int, default=None)
    parser.add_argument("--journal", default=None, help="Journal or source title")
    parser.add_argument("--document-type", default=None)
    parser.add_argument(
        "--source-type",
        action="append",
        dest="source_types",
        default=None,
        help="Source category such as CSSCI, SCI, EI, CSCD, AMI, or 北大核心",
    )
    parser.add_argument("--author", default=None, help="Author filter")
    parser.add_argument("--institution", default=None, help="Institution filter")


def _build_parser() -> argparse.ArgumentParser:
    """Build the unified cnki-mcp argument parser."""
    parser = argparse.ArgumentParser(
        prog="cnki-mcp",
        description="CNKI MCP server and command-line tools",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {_package_version()}",
    )
    commands = parser.add_subparsers(dest="command")

    serve_parser = commands.add_parser("serve", help="Start the MCP server")
    serve_parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "http"],
        default="http",
    )
    serve_parser.add_argument("--host", default=DEFAULT_HOST)
    serve_parser.add_argument("--port", type=int, default=DEFAULT_PORT)

    login_parser = commands.add_parser("login", help="Log in to CNKI")
    _add_profile_option(login_parser)
    _add_output_option(login_parser)

    logout_parser = commands.add_parser("logout", help="Log out from CNKI")
    _add_profile_option(logout_parser)
    _add_output_option(logout_parser)

    tool_parser = commands.add_parser("tool", help="Run a CNKI tool")
    tools = tool_parser.add_subparsers(dest="tool_command", required=True)

    search_parser = tools.add_parser(
        "search",
        help="Search CNKI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=PROFESSIONAL_SEARCH_GUIDE,
    )
    search_parser.add_argument("query", nargs="?", help="One-box search text")
    search_parser.add_argument(
        "--advanced",
        metavar="EXPRESSION",
        default=None,
        help="CNKI professional-search expression",
    )
    _add_profile_option(search_parser)
    _add_output_option(search_parser)
    _add_search_filters(search_parser)

    info_parser = tools.add_parser("info", help="Get detailed article information")
    info_parser.add_argument("url", nargs="?", help="CNKI article detail URL")
    info_parser.add_argument("--title", default=None, help="Article title")
    info_parser.add_argument(
        "--author",
        action="append",
        dest="authors",
        default=None,
        help="Article author; repeat for multiple authors",
    )
    info_parser.add_argument("--year", type=int, default=None)
    info_parser.add_argument(
        "--source",
        "--journal",
        dest="source",
        default=None,
        help="Article source or journal title",
    )
    info_parser.add_argument("--document-type", default=None)
    info_parser.add_argument("--limit", type=int, default=10)
    _add_profile_option(info_parser)
    _add_output_option(info_parser)

    return parser


def _option_was_supplied(raw_args: list[str], option: str) -> bool:
    """Return whether an option appears explicitly in raw arguments."""
    return any(value == option or value.startswith(f"{option}=") for value in raw_args)


def _validate_serve_args(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    raw_args: list[str],
) -> None:
    """Reject network-only options when stdio is selected."""
    if args.transport != "stdio":
        return
    if _option_was_supplied(raw_args, "--host") or _option_was_supplied(
        raw_args, "--port"
    ):
        parser.error("--host and --port are not allowed with stdio transport")


def _run_server(transport: str, host: str, port: int) -> int:
    """Build and run the selected MCP transport."""
    if transport == "sse":
        print("提示：SSE 可以使用，但建议优先选择 HTTP。", file=sys.stderr)
    server = create_mcp_server(transport, host=host, port=port)
    try:
        server.run(transport=TRANSPORT_MAP[transport])
    except KeyboardInterrupt:
        return 0
    return 0


def _search_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    """Collect explicitly configured search options."""
    kwargs: dict[str, Any] = {"limit": args.limit}
    if args.sort_by:
        kwargs["sort_by"] = args.sort_by
    for key in (
        "year_from",
        "year_to",
        "journal",
        "document_type",
        "source_types",
        "author",
        "institution",
    ):
        value = getattr(args, key)
        if value:
            kwargs[key] = value
    return kwargs


def _run_search(parser: argparse.ArgumentParser, args: argparse.Namespace) -> Any:
    """Run one-box or professional search according to the selected input."""
    if bool(args.query) == bool(args.advanced):
        parser.error("provide either one-box query text or --advanced expression")
    client = CnkiClient(profile=args.profile)
    kwargs = _search_kwargs(args)
    if args.advanced:
        results = client.search(args.advanced, **kwargs)
    else:
        results = client.search_basic(args.query, **kwargs)
    return [result.to_public_dict() for result in results]


def _is_cnki_url(value: str) -> bool:
    """Return whether a value is an absolute CNKI HTTP URL."""
    parsed = urlparse(value)
    hostname = (parsed.hostname or "").casefold()
    return parsed.scheme in {"http", "https"} and hostname.endswith("cnki.net")


def _run_info(parser: argparse.ArgumentParser, args: argparse.Namespace) -> Any:
    """Parse a detail URL or locate an article from citation fields."""
    if bool(args.url) == bool(args.title):
        parser.error("provide either a CNKI URL or --title")
    client = CnkiClient(profile=args.profile)
    if args.url:
        if any((args.authors, args.year, args.source, args.document_type)):
            parser.error("citation options cannot be combined with a direct URL")
        if not _is_cnki_url(args.url):
            parser.error("info URL must be an absolute cnki.net URL")
        return asdict(client.get_metadata(args.url))
    result = client.lookup_metadata(
        args.title,
        authors=args.authors,
        year=args.year,
        source=args.source,
        document_type=args.document_type,
        limit=args.limit,
    )
    return asdict(result)


def main(argv: list[str] | None = None) -> int:
    """Run the unified cnki-mcp CLI."""
    raw_args = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    args = parser.parse_args(raw_args)

    if args.command is None:
        return _run_server("http", DEFAULT_HOST, DEFAULT_PORT)
    if args.command == "serve":
        _validate_serve_args(parser, args, raw_args)
        return _run_server(args.transport, args.host, args.port)

    try:
        if args.command == "tool" and args.tool_command == "search":
            data = _run_search(parser, args)
        elif args.command == "tool" and args.tool_command == "info":
            data = _run_info(parser, args)
        elif args.command == "login":
            client = CnkiClient(profile=args.profile)
            result = client.login()
            data = {
                "success": result.success,
                "message": result.message,
                "profile": result.auth_state.profile,
            }
        elif args.command == "logout":
            client = CnkiClient(profile=args.profile)
            client.logout()
            data = {
                "success": True,
                "message": "logged out",
                "profile": client.current_profile,
            }
        else:
            parser.error("unknown command")
    except CnkiMcpError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(_format_output(data, args.output))
    return 0


__all__ = ["_format_output", "main"]
