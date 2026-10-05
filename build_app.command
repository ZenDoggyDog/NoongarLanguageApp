#!/bin/bash
set -e

cd "$(dirname "$0")"
python3 -m PyInstaller \
  --clean \
  --noconfirm \
  --windowed \
  --onedir \
  --name "Noongar Language Learner" \
  --add-data "Noongar categories.csv:." \
  --add-data "web/audio:audio" \
  noongar.py

echo
echo "App created at:"
echo "$(pwd)/dist/Noongar Language Learner.app"
