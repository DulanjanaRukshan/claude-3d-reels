#!/usr/bin/env bash
# One-time setup in an empty project folder. Needs: node 18+, python 3.10+, ffmpeg, Google Chrome.
set -e
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p audio build assets sfx
[ -f package.json ] || npm init -y >/dev/null
npm i three puppeteer-core @fontsource/fredoka
pip install kokoro-onnx soundfile sherpa-onnx numpy 2>/dev/null || pip install --break-system-packages kokoro-onnx soundfile sherpa-onnx numpy
for f in render.js voice.py mix.py transcribe.py; do [ -f "$f" ] || cp "$SKILL_DIR/scripts/$f" .; done
[ -f comp.html ] || cp "$SKILL_DIR/templates/comp.html" comp.html
cd assets
[ -f kokoro.onnx ] || curl -fsSL -o kokoro.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
[ -f voices.bin ] || curl -fsSL -o voices.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
if [ ! -d sherpa-onnx-whisper-base.en ]; then
  curl -fsSL -o w.tar.bz2 https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-base.en.tar.bz2
  tar xjf w.tar.bz2 && rm w.tar.bz2
fi
cd ..
command -v ffmpeg >/dev/null || echo "WARNING: ffmpeg not found - install it (brew install ffmpeg / apt install ffmpeg)"
echo "Setup done."
