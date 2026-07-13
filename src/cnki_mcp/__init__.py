from importlib.metadata import PackageNotFoundError, version

from .core import CnkiClient

try:
    __version__ = version("cnki-mcp")
except PackageNotFoundError:
    __version__ = "0.1.0"


def main() -> None:
    """Run the unified cnki-mcp command-line interface."""
    from .cli.main import main as cli_main

    raise SystemExit(cli_main())


__all__ = ["CnkiClient", "__version__", "main"]
