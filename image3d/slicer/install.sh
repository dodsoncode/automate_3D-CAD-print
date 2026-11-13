#!/usr/bin/env bash
# Installs what "Slice for P1S" needs: Node, the OrcaSlicer engine (npm) and the Bambu profiles, then proves the
# engine runs by slicing a built-in 10 mm cube.
# Run from image3d/ (render.yaml build step):  bash slicer/install.sh
# Idempotent. Always exits 0: the slicer is optional, the page shows "Slicer unavailable" when this failed.
# Last line printed: "SLICER INSTALL: ok" or "SLICER INSTALL: failed at <step>" (after the last 20 lines of that
# step's output). On success it writes slicer/.install_ok (OrcaSlicer commit + Node version); slicing.available()
# needs that file.

NODE_VERSION="v22.23.4"          # Node 22 LTS, downloaded when the PATH has no node >= 18
NODE_MIN_MAJOR=18
ORCA_REPO="https://github.com/SoftFever/OrcaSlicer"

SLICER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORCA_COMMIT="$(tr -d '[:space:]' < "$SLICER_DIR/ORCA_COMMIT")"     # profiles pinned to this commit (one source of truth)
PROFILES_DIR="$SLICER_DIR/resources/profiles"
MARKER="$SLICER_DIR/.install_ok"
NODE_TMP=""
PROFILES_TMP=""
SMOKE_TMP=""
LOGDIR="$(mktemp -d)"

# the commit the previous successful run installed (empty when none), then forget that run
OLD_COMMIT=""
[ -f "$MARKER" ] && OLD_COMMIT="$(sed -n 's/^orca_commit=//p' "$MARKER" | head -n 1)"
rm -f "$MARKER"

cleanup() {
  [ -n "$NODE_TMP" ] && rm -rf "$NODE_TMP"
  [ -n "$PROFILES_TMP" ] && rm -rf "$PROFILES_TMP"
  [ -n "$SMOKE_TMP" ] && rm -rf "$SMOKE_TMP"
  rm -rf "$LOGDIR"
  return 0
}
trap cleanup EXIT

fail() {
  tail -n 20 "$LOGDIR/$1.log" 2>/dev/null
  echo "SLICER INSTALL: failed at $1"
  exit 0
}

# the node the slicer will use: the local one when present (slicing.node_path() does the same), else the PATH's
use_node() {
  if [ -x "$SLICER_DIR/.node/bin/node" ]; then
    export PATH="$SLICER_DIR/.node/bin:$PATH"
  fi
}

node_major() {
  node -p 'process.versions.node.split(".")[0]' 2>/dev/null
}

# ---- step 1: node (>= 18) ----
step_node() {
  use_node
  local major
  major="$(node_major)"
  if [ -n "$major" ] && [ "$major" -ge "$NODE_MIN_MAJOR" ] 2>/dev/null; then
    echo "using node $(node -v)"
    return 0
  fi
  echo "no node >= $NODE_MIN_MAJOR on the PATH (found: ${major:-none}); downloading $NODE_VERSION"
  local name="node-$NODE_VERSION-linux-x64"
  local base="https://nodejs.org/dist/$NODE_VERSION"
  # Work inside slicer/ so the final mv is a same-filesystem rename: an interrupted run never leaves a half-made .node
  NODE_TMP="$(mktemp -d "$SLICER_DIR/.node.tmp.XXXXXX")" || return 1
  curl -fsSL "$base/$name.tar.xz" -o "$NODE_TMP/$name.tar.xz" || return 1
  curl -fsSL "$base/SHASUMS256.txt" -o "$NODE_TMP/SHASUMS256.txt" || return 1
  (cd "$NODE_TMP" && grep " $name.tar.xz\$" SHASUMS256.txt | sha256sum -c -) || return 1
  mkdir "$NODE_TMP/extract" || return 1
  tar -xJf "$NODE_TMP/$name.tar.xz" -C "$NODE_TMP/extract" --strip-components=1 || return 1
  [ -x "$NODE_TMP/extract/bin/node" ] || return 1
  rm -rf "$SLICER_DIR/.node" || return 1
  mv "$NODE_TMP/extract" "$SLICER_DIR/.node" || return 1
  use_node
}

# ---- step 2: the engine from npm ----
step_npm() {
  use_node
  command -v npm >/dev/null 2>&1 || { echo "npm not found"; return 1; }
  if [ -d "$SLICER_DIR/node_modules/orcaslicer-addon" ] && [ "$SLICER_DIR/node_modules/.package-lock.json" -nt "$SLICER_DIR/package-lock.json" ]; then
    echo "engine already installed"
    return 0
  fi
  (cd "$SLICER_DIR" && npm ci --omit=dev --no-audit --no-fund) || return 1
  [ -d "$SLICER_DIR/node_modules/orcaslicer-addon" ] || return 1
}

# ---- step 3: Bambu profiles at the pinned commit ----
step_profiles() {
  if [ -f "$PROFILES_DIR/BBL.json" ] && [ -d "$PROFILES_DIR/BBL" ] \
     && [ "$(cat "$PROFILES_DIR/.orca_commit" 2>/dev/null)" = "$ORCA_COMMIT" ] \
     && { [ -z "$OLD_COMMIT" ] || [ "$OLD_COMMIT" = "$ORCA_COMMIT" ]; }; then
    echo "profiles already at $ORCA_COMMIT"
    return 0
  fi
  PROFILES_TMP="$(mktemp -d)" || return 1
  local repo="$PROFILES_TMP/repo"
  git clone --quiet --depth 1 --filter=blob:none --sparse "$ORCA_REPO" "$repo" || return 1
  git -C "$repo" sparse-checkout set resources/profiles/BBL || return 1
  git -C "$repo" fetch --quiet --depth 1 --filter=blob:none origin "$ORCA_COMMIT" || return 1
  git -C "$repo" checkout --quiet FETCH_HEAD || return 1
  git -C "$repo" show "FETCH_HEAD:resources/profiles/BBL.json" > "$PROFILES_TMP/BBL.json" || return 1
  [ -s "$PROFILES_TMP/BBL.json" ] && [ -d "$repo/resources/profiles/BBL" ] || return 1
  rm -rf "$PROFILES_DIR" || return 1
  mkdir -p "$PROFILES_DIR" || return 1
  cp -r "$repo/resources/profiles/BBL" "$PROFILES_DIR/BBL" || return 1
  cp "$PROFILES_TMP/BBL.json" "$PROFILES_DIR/BBL.json" || return 1
  echo "$ORCA_COMMIT" > "$PROFILES_DIR/.orca_commit" || return 1
}

# ---- step 4: slice a 10 mm cube with the default settings ----
step_smoke() {
  use_node
  local py
  py="$(command -v python3 || command -v python)" || { echo "python not found"; return 1; }
  SMOKE_TMP="$(mktemp -d)" || return 1
  (cd "$SLICER_DIR/.." && "$py" -c 'import json, slicing; print(json.dumps(slicing.settings_for({})))') > "$SMOKE_TMP/settings.json" || return 1
  (cd "$SLICER_DIR" && node slice_job.js "$SLICER_DIR/smoke_cube.stl" "$SMOKE_TMP/out.gcode.3mf" "$SMOKE_TMP/settings.json" 2>&1 | tail -n 40) || true
  [ -s "$SMOKE_TMP/out.gcode.3mf" ] || { echo "the engine wrote no file"; return 1; }
  "$py" -c 'import sys, zipfile; sys.exit(0 if "Metadata/plate_1.gcode" in zipfile.ZipFile(sys.argv[1]).namelist() else 1)' "$SMOKE_TMP/out.gcode.3mf" \
    || { echo "no Metadata/plate_1.gcode in the output"; return 1; }
  rm -rf "$SLICER_DIR/.orcaslicercli"
  printf 'orca_commit=%s\nnode=%s\n' "$ORCA_COMMIT" "$(node -v)" > "$MARKER" || return 1
}

for step in node npm profiles smoke; do
  "step_$step" > "$LOGDIR/$step.log" 2>&1 || fail "$step"
  tail -n 3 "$LOGDIR/$step.log"
done
echo "SLICER INSTALL: ok"
exit 0
