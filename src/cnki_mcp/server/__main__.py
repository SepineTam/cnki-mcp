#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 - Present Sepine Tam, Inc. All Rights Reserved
#
# @Author : Sepine Tam (谭淞)
# @Email  : sepinetam@gmail.com
# @File   : server/__main__.py

"""Module entry point for the default HTTP MCP server."""

from ..cli.main import main

if __name__ == "__main__":
    raise SystemExit(main(["serve"]))
