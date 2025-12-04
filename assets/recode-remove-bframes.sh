#!/usr/bin/env bash
# recode-remove-bframes.sh – Transcode MP4 to remove B-frames while preserving quality
# Usage: ./recode-remove-bframes.sh input.mp4
# Output: input-b0.mp4 (or input-nobframes.mp4)

set -euo pipefail

[[ $# -eq 1 && -f "$1" ]] || { echo "Usage: $0 input.mp4"; exit 1; }

INPUT="$1"
BASENAME="${INPUT%.*}"
EXTENSION="${INPUT##*.}"
OUTPUT="${BASENAME}-b0.${EXTENSION}"

if [[ -f "$OUTPUT" ]]; then
    echo "Output file already exists: $OUTPUT" >&2
    exit 1
fi

echo "Recoding $INPUT to remove B-frames..."
echo "Input:  $INPUT"
echo "Output: $OUTPUT"
echo ""

# Extract original video bitrate for 2-pass encoding
ORIG_BITRATE=$(ffprobe -v error -select_streams v:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 "$INPUT")

if [[ -z "$ORIG_BITRATE" || "$ORIG_BITRATE" == "N/A" ]]; then
    echo "Could not detect original bitrate; using CRF 18 for near-lossless quality" >&2
    ffmpeg -i "$INPUT" \
        -c:v libx264 \
        -preset slower \
        -crf 18 \
        -bf 0 \
        -c:a copy \
        "$OUTPUT"
else
    TARGET_BITRATE=$((ORIG_BITRATE / 1000))  # convert to kbps
    echo "Matching original video bitrate: ${TARGET_BITRATE}k (2-pass encode)"
    echo ""
    
    # Pass 1: analysis
    echo "Running pass 1/2..."
    ffmpeg -y -i "$INPUT" \
        -c:v libx264 \
        -preset slower \
        -b:v "${TARGET_BITRATE}k" \
        -bf 0 \
        -pass 1 \
        -an \
        -f null /dev/null
    
    echo "Running pass 2/2..."
    # Pass 2: final encode
    ffmpeg -i "$INPUT" \
        -c:v libx264 \
        -preset slower \
        -b:v "${TARGET_BITRATE}k" \
        -bf 0 \
        -pass 2 \
        -c:a copy \
        "$OUTPUT"
    
    # Clean up pass log files
    rm -f ffmpeg2pass-0.log ffmpeg2pass-0.log.mbtree
fi

echo ""
echo "Transcode complete: $OUTPUT"

# Show comparison info if mp4-info.sh is available
if [[ -x "$(dirname "$0")/mp4-info.sh" ]]; then
    echo ""
    echo "Original:"
    "$(dirname "$0")/mp4-info.sh" "$INPUT" | grep -E "(File size|Duration|bitrate|B-frames)" || true
    echo ""
    echo "Recoded:"
    "$(dirname "$0")/mp4-info.sh" "$OUTPUT" | grep -E "(File size|Duration|bitrate|B-frames)" || true
fi
