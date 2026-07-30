#!/usr/bin/env sh
set -eu

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

.venv/bin/python -m pip install -r requirements.txt
exec .venv/bin/python -m aurora_player "$@"
