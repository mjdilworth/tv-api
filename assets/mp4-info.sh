#!/usr/bin/env bash
# mp4-info-fast.sh – correct + super fast B-frame detection (<1 s)

set -euo pipefail

format_fps() {
  local value="$1"
  case "$value" in
    60000/1001) echo "59.94 fps" ; return ;;
    30000/1001) echo "29.97 fps" ; return ;;
    24000/1001) echo "23.98 fps" ; return ;;
  esac
  if [[ "$value" == */* ]]; then
    local num=${value%/*}
    local den=${value#*/}
    if [[ "$den" != 0 ]]; then
      awk -v n="$num" -v d="$den" 'BEGIN {printf "%.2f fps", n/d}'
      return
    fi
  fi
  printf "%s fps" "$value"
}

[[ $# -eq 1 && -f "$1" ]] || { echo "Usage: $0 file.mp4"; exit 1; }

FILE="$1"
BASE=$(basename "$FILE")

echo "=================================================="
echo "          MP4 INFO: $BASE"
echo "=================================================="

# Fast general info
echo "File size       : $(du -h "$FILE" | cut -f1)"
ffprobe -v error -show_entries format=duration,bit_rate -of csv=p=0 "$FILE" | \
  awk -F, '{printf "Duration        : %d:%02d:%02d (%.2f s)\nTotal bitrate   : %.0f kbps\n\n", $1/3600, ($1%3600)/60, $1%60, $1, $2/1000}'

# Video stream details
declare -A VIDEO_META
while IFS='=' read -r key value; do
  [[ -z "$key" ]] && continue
  VIDEO_META[$key]="$value"
done < <(ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,profile,level,width,height,r_frame_rate,pix_fmt,bit_rate \
  -of default=noprint_wrappers=1 "$FILE")

codec="${VIDEO_META[codec_name]:-unknown}"
profile="${VIDEO_META[profile]:-unknown}"
level="${VIDEO_META[level]:-unknown}"
width="${VIDEO_META[width]:-?}"
height="${VIDEO_META[height]:-?}"
pixel_fmt="${VIDEO_META[pix_fmt]:-unknown}"
frame_rate="$(format_fps "${VIDEO_META[r_frame_rate]:-0/1}")"
video_bitrate="${VIDEO_META[bit_rate]:-0}"

printf "Codec           : %s\n" "$codec"
printf "Profile         : %s\n" "$profile"
printf "Level           : %s\n" "$level"
printf "Resolution      : %sx%s\n" "$width" "$height"
printf "Pixel format    : %s\n" "$pixel_fmt"
printf "Frame rate      : %s\n" "$frame_rate"
if [[ "$video_bitrate" =~ ^[0-9]+$ && "$video_bitrate" -gt 0 ]]; then
  mbps=$(awk -v b="$video_bitrate" 'BEGIN {printf "%.2f", b/1000000}')
  printf "Video bitrate   : %s bps (%.2f Mbps)\n" "$video_bitrate" "$mbps"
else
  printf "Video bitrate   : %s bps\n" "$video_bitrate"
fi

# Audio (if any)
if ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$FILE" >/dev/null 2>&1; then
  echo -e "\nAudio streams   :"
  ffprobe -v error -select_streams a -show_entries stream=codec_name,channels,sample_rate,bit_rate \
    -of default=noprint_wrappers=1 "$FILE" | sed 's/^/  • /'
fi

# Reliable B-frame detection by inspecting early frame types
echo -e "\nContains B-frames: \c"
frame_sample="$(ffprobe -v error -select_streams v:0 \
  -show_entries frame=pict_type -read_intervals "%+#400" \
  -of csv=p=0 "$FILE")"
if grep -q 'B' <<< "$frame_sample"; then
  echo "YES"
else
  echo "NO"
fi

# Bonus: first 40 frame types (still fast)
echo -e "\nFirst 40 frame types (I/P/B):"
ffprobe -v error -show_entries frame=pict_type \
  -select_streams v:0 -of csv=p=0 "$FILE" | head -40 | tr '\n' ' ' ; echo

echo -e "\n=================================================="