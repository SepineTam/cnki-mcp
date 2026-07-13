#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : tests/test_package.py

"""Tests for the top-level cnki_mcp package."""

from unittest.mock import patch

import pytest

import cnki_mcp
from cnki_mcp import CnkiClient


def test_package_exports_cnki_client() -> None:
    """CnkiClient is available from the package root."""
    assert CnkiClient is not None
    assert isinstance(cnki_mcp.CnkiClient, type)


def test_package_version_is_string() -> None:
    """__version__ is a string."""
    assert isinstance(cnki_mcp.__version__, str)
    assert cnki_mcp.__version__


def test_package_main_is_callable() -> None:
    """main is callable."""
    assert callable(cnki_mcp.main)


def test_main_delegates_to_unified_cli() -> None:
    """The package entry point delegates to the unified CLI."""
    with patch("cnki_mcp.cli.main.main", return_value=7) as mock_cli_main:
        with pytest.raises(SystemExit) as exc_info:
            cnki_mcp.main()

    assert exc_info.value.code == 7
    mock_cli_main.assert_called_once_with()
