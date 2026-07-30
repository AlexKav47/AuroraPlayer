#!/usr/bin/env sh
set -eu

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

.venv/bin/python -m pip install -r requirements.txt pyinstaller
.venv/bin/pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name AuroraPlayer \
  --icon aurora_player/assets/aurora-player.ico \
  --add-data "aurora_player/skins:aurora_player/skins" \
  --add-data "aurora_player/extensions:aurora_player/extensions" \
  --add-data "aurora_player/assets:aurora_player/assets" \
  launcher.py

printf '%s\n' "Built dist/AuroraPlayer/AuroraPlayer"
printf '%s\n' "libVLC must remain installed on the target computer."
