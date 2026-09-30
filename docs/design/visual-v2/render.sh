#!/usr/bin/env bash
# Export each v2 board to a 3840×2400 PNG (1920×1200 @2x) with headless Chrome.
# Usage: docs/design/visual-v2/render.sh [board-id ...]
# Headless Chrome on macOS can stay alive after writing the screenshot, so each
# export runs in the background and is stopped once the PNG has been written.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
chrome="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
profile="$(mktemp -d)"
trap 'rm -rf "$profile"' EXIT
mkdir -p "$here/png"

boards=("$@")
if [ ${#boards[@]} -eq 0 ]; then
  boards=(foundations catalog reader review loop)
fi

render_one() {
  local id="$1" out="$2" pid size
  rm -f "$out"
  "$chrome" --headless=new --disable-gpu --hide-scrollbars --no-first-run \
    --user-data-dir="$profile" --force-device-scale-factor=2 \
    --window-size=1920,1200 --screenshot="$out" \
    "file://$here/index.html?export=$id" >/dev/null 2>&1 &
  pid=$!
  for _ in $(seq 1 150); do
    if [ -s "$out" ]; then
      size=$(stat -f %z "$out")
      sleep 0.4
      [ "$size" = "$(stat -f %z "$out")" ] && break
    fi
    sleep 0.2
  done
  kill "$pid" 2>/dev/null || true
  wait "$pid" 2>/dev/null || true
  [ -s "$out" ] || { echo "failed: $id" >&2; return 1; }
}

for id in "${boards[@]}"; do
  case "$id" in
    foundations) name="v2-00-foundations" ;;
    catalog) name="v2-01-catalog" ;;
    reader) name="v2-02-reader" ;;
    review) name="v2-03-review" ;;
    loop) name="v2-04-mobile-loop" ;;
    *) echo "unknown board: $id" >&2; exit 1 ;;
  esac
  render_one "$id" "$here/png/$name.png"
  echo "$name.png"
done
