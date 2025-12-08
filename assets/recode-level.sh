#!/usr/bin/env bash
# Recode H.264 video to lower profile level for compatibility with Google TV Streamer
# Usage: ./recode-level.sh input.mp4 [output.mp4]

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 input.mp4 [output.mp4]" >&2
    echo "" >&2
    echo "Recodes H.264 video from High@L6.0 to High@L5.1 for Google TV compatibility" >&2
    exit 1
fi

INPUT="$1"
OUTPUT="${2:-${INPUT%.mp4}-recoded.mp4}"

if [[ ! -f "$INPUT" ]]; then
    echo "Error: Input file '$INPUT' not found" >&2
    exit 1
fi

echo "Recoding: $INPUT"
echo "Output:   $OUTPUT"
echo ""
echo "Settings:"
echo "  Profile: High"
echo "  Level:   5.1 (was 6.0)"
echo "  Codec:   H.264"
echo "  B-frames: None (baseline)"
echo "  Quality: Match original bitrate"
echo "  Audio:   Copy (no re-encode)"
echo ""

ffmpeg -i "$INPUT" \
    -c:v libx264 \
    -profile:v high \
    -level:v 5.1 \
    -preset slow \
    -bf 0 \
    -b:v 44M \
    -maxrate 44M \
    -bufsize 88M \
    -pix_fmt yuv420p \
    -c:a copy \
    -movflags +faststart \
    -x264-params "level=5.1:vbv-maxrate=44000:vbv-bufsize=88000" \
    "$OUTPUT"

echo ""
echo "Done! Recoded video saved to: $OUTPUT"
echo ""
echo "Original size: $(du -h "$INPUT" | cut -f1)"
echo "New size:      $(du -h "$OUTPUT" | cut -f1)"
