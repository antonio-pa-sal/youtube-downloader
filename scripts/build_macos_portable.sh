#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-venv/bin/python}"
APP_NAME="YouTubeDownloader"
PORTABLE_DIR="dist/${APP_NAME}-macos-arm64-portable"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python virtual environment not found at: $PYTHON_BIN" >&2
  echo "Create it with: python -m venv venv && source venv/bin/activate" >&2
  exit 1
fi

"$PYTHON_BIN" -m pip install -r requirements.txt -r requirements-build.txt

FFMPEG_BIN="$("$PYTHON_BIN" -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')"
NODE_BIN="$("$PYTHON_BIN" -c 'import nodejs_wheel, pathlib; print(pathlib.Path(nodejs_wheel.__file__).parent / "bin" / "node")')"

if [[ ! -x "$FFMPEG_BIN" ]]; then
  echo "Portable ffmpeg binary not found: $FFMPEG_BIN" >&2
  exit 1
fi

if [[ ! -x "$NODE_BIN" ]]; then
  echo "Portable node binary not found: $NODE_BIN" >&2
  exit 1
fi

rm -rf "build" "dist/${APP_NAME}" "$PORTABLE_DIR"

"$PYTHON_BIN" -m PyInstaller \
  --noconfirm \
  --clean \
  --onedir \
  --name "$APP_NAME" \
  --collect-all yt_dlp \
  --collect-all curl_cffi \
  --collect-all pytubefix \
  youtube_downloader.py

mkdir -p "$PORTABLE_DIR"
cp -R "dist/${APP_NAME}/." "$PORTABLE_DIR/"
mkdir -p "$PORTABLE_DIR/bin"
cp "$FFMPEG_BIN" "$PORTABLE_DIR/bin/ffmpeg"
cp "$NODE_BIN" "$PORTABLE_DIR/bin/node"
chmod +x "$PORTABLE_DIR/${APP_NAME}" "$PORTABLE_DIR/bin/ffmpeg" "$PORTABLE_DIR/bin/node"

cat > "$PORTABLE_DIR/README_PORTABLE_MACOS.txt" <<'EOF'
YouTubeDownloader macOS Apple silicon portable build

Run from Terminal:

  ./YouTubeDownloader

Validate bundled dependencies without downloading:

  ./YouTubeDownloader --self-test

If macOS blocks the executable because it is unsigned, run:

  xattr -dr com.apple.quarantine .
  ./YouTubeDownloader

This folder includes:

  bin/ffmpeg
  bin/node

Keep the bin folder next to the YouTubeDownloader executable.
EOF

echo "Portable build created:"
echo "  $PORTABLE_DIR"
