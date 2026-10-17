#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_dir"
if [[ ! -x .venv/bin/python ]]; then
    echo 'Najpierw uruchom: bash install_linux.sh' >&2
    exit 1
fi
if [[ $# -eq 0 ]]; then
    set -- --camera /dev/video2 --laser-color green --green-min 180 --green-delta 45
fi
exec .venv/bin/python aimlab_irl_camera_mvp.py "$@"
