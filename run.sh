#!/bin/sh
# Avvio su Linux/macOS: ./run.sh [file.pdf]
cd "$(dirname "$0")" && exec python3 -m wpdf "$@"
