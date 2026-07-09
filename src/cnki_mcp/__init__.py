from importlib.metadata import PackageNotFoundError, version

from .core import CnkiClient

try:
    __version__ = version("cnki-mcp")
except PackageNotFoundError:
    __version__ = "0.1.0"


def main() -> None:
    """Start the CNKI MCP server."""
    from .server.cnki_mcp_server import mcp_server

    mcp_server.run()


__all__ = ["CnkiClient", "__version__", "main"]
