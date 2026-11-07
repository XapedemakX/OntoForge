#!/bin/sh
# Assemble les images horodatées du screencast en MP4 30 i/s (H.264). Usage : sh tools/video/assemble.sh sortie.mp4
set -e
D="$(cd "$(dirname "$0")/../../journal/L18/video" && pwd)"; OUT="${1:-$D/ontoforge-demo.mp4}"
cd "$D"
ffmpeg -y -loglevel error -f concat -safe 0 -i frames.txt -vf "scale=1920:1080:flags=lanczos,fps=30,format=yuv420p" -c:v libx264 -crf 20 -preset veryfast -movflags +faststart tmp-out.mp4
mv tmp-out.mp4 "$OUT"; echo "$OUT"
