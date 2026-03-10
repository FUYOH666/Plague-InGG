#!/bin/bash
set -e
cd "$(dirname "$0")"
uv run python seed/main.py
