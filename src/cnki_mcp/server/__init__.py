#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : server/__init__.py

"""MCP server package."""

from .cnki_mcp_server import create_mcp_server

__all__ = ["create_mcp_server"]
