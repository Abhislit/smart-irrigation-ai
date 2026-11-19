#!/bin/sh
# Run any project script with the local dependency folder on the path.
#   ./run.sh src/train.py
cd "$(dirname "$0")" || exit 1
PYTHONPATH="$PWD/.deps" exec python3 "$@"
