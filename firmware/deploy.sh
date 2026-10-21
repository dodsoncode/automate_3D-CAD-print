#!/usr/bin/env bash
# Copy firmware/src/*.py to the ESP32 with mpremote.   Usage: PORT=/dev/ttyUSB0 ./deploy.sh
set -euo pipefail
cd "$(dirname "$0")/src"
PORT="${PORT:-auto}"
args=()
for f in config.py pca9685.py servos.py gait.py drive.py webctl.py calibrate.py main.py; do
  args+=("cp" "$f" ":$f" "+")
done
unset 'args[${#args[@]}-1]'    # drop the trailing "+"
mpremote connect "$PORT" "${args[@]}" + reset
echo "Deployed. Open the REPL with: mpremote connect $PORT repl"
