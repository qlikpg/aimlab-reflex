#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_dir"
.venv/bin/python -m pip install -r aimlab_voice_requirements.txt
.venv/bin/python setup_voice.py
