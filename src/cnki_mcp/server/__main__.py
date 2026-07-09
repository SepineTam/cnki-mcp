#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : server/__main__.py

"""Command-line entry point for the MCP server."""

from .cnki_mcp_server import mcp_server

if __name__ == "__main__":
    mcp_server.run()
