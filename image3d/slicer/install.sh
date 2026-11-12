#!/usr/bin/env bash
# Installs what "Slice for P1S" needs: Node, the OrcaSlicer engine (npm) and the Bambu profiles.
# Run from image3d/ (render.yaml build step):  bash slicer/install.sh
# Idempotent. Always exits 0: the slicer is optional, the page shows "Slicer unavailable" when this failed.
# Last line printed: "SLICER INSTALL: ok" or "SLICER INSTALL: failed at <step>".

NODE_VERSION="v22.23.4"          # Node 22 LTS
ORCA_REPO="https://github.com/SoftFever/OrcaSlicer"
ORCA_COMMIT="47a17ad9a33af7871bdbf21935bc2c1a6a5e488f"   # profiles pinned to this commit

SLICER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILES_DIR="$SLICER_DIR/resources/profiles"
TMP=""

cleanup() { [ -n "$TMP" ] && rm -rf "$TMP"; }
trap cleanup EXIT

fail() {
  echo "SLICER INSTALL: failed at $1"
  exit 0
}

# ---- step 1: node ----
step_node() {
  if command -v node >/dev/null 2>&1 || [ -x "$SLICER_DIR/.node/bin/node" ]; then
    return 0
  fi
  local name="node-$NODE_VERSION-linux-x64"
  local base="https://nodejs.org/dist/$NODE_VERSION"
  TMP="$(mktemp -d)" || return 1
  curl -fsSL "$base/$name.tar.xz" -o "$TMP/$name.tar.xz" || return 1
  curl -fsSL "$base/SHASUMS256.txt" -o "$TMP/SHASUMS256.txt" || return 1
  (cd "$TMP" && grep " $name.tar.xz\$" SHASUMS256.txt | sha256sum -c - >/dev/null 2>&1) || return 1
  mkdir -p "$SLICER_DIR/.node" || return 1
  tar -xJf "$TMP/$name.tar.xz" -C "$SLICER_DIR/.node" --strip-components=1 || return 1
  [ -x "$SLICER_DIR/.node/bin/node" ] || return 1
}

# ---- step 2: the engine from npm ----
step_npm() {
  if [ -x "$SLICER_DIR/.node/bin/node" ]; then
    export PATH="$SLICER_DIR/.node/bin:$PATH"
  fi
  command -v npm >/dev/null 2>&1 || return 1
  (cd "$SLICER_DIR" && npm ci --omit=dev --no-audit --no-fund >/dev/null 2>&1) || return 1
  [ -d "$SLICER_DIR/node_modules/orcaslicer-addon" ] || return 1
}

# ---- step 3: Bambu profiles at the pinned commit ----
step_profiles() {
  if [ -f "$PROFILES_DIR/BBL.json" ] && [ -d "$PROFILES_DIR/BBL" ]; then
    return 0
  fi
  TMP="$(mktemp -d)" || return 1
  local repo="$TMP/repo"
  git clone --quiet --depth 1 --filter=blob:none --sparse "$ORCA_REPO" "$repo" || return 1
  git -C "$repo" sparse-checkout set resources/profiles/BBL || return 1
  git -C "$repo" fetch --quiet --depth 1 --filter=blob:none origin "$ORCA_COMMIT" || return 1
  git -C "$repo" checkout --quiet FETCH_HEAD || return 1
  git -C "$repo" show "FETCH_HEAD:resources/profiles/BBL.json" > "$TMP/BBL.json" || return 1
  [ -s "$TMP/BBL.json" ] && [ -d "$repo/resources/profiles/BBL" ] || return 1
  rm -rf "$PROFILES_DIR" || return 1
  mkdir -p "$PROFILES_DIR" || return 1
  cp -r "$repo/resources/profiles/BBL" "$PROFILES_DIR/BBL" || return 1
  cp "$TMP/BBL.json" "$PROFILES_DIR/BBL.json" || return 1
}

step_node || fail node
step_npm || fail npm
step_profiles || fail profiles
echo "SLICER INSTALL: ok"
exit 0
