#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_dir"

echo 'Instalowanie Pythona, obsługi środowisk i bibliotek kamery...'
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip python3-gi gir1.2-gtk-3.0 libgl1 libglib2.0-0t64 librsvg2-2 libcairo2 v4l-utils pulseaudio-utils

python3 -m venv .venv
.venv/bin/python -m pip install -r aimlab_requirements.txt
.venv/bin/python -c 'import cv2, numpy; print("Gotowe. OpenCV:", cv2.__version__, "NumPy:", numpy.__version__)'
echo
echo 'Wykryte kamery:'
v4l2-ctl --list-devices || true
echo
echo "Uruchom projekt: bash \"$project_dir/start_linux.sh\""
