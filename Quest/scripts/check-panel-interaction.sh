#!/usr/bin/env bash
# Human-in-the-loop check of actual controller behavior; records no URLs or tokens.
set -euo pipefail

if ! adb get-state >/dev/null 2>&1; then
  printf 'DEVICE=unavailable\nRESULT=not_run\nConnect one authorized Quest before running this check.\n'
  exit 2
fi
if [[ "${1:-}" == "--check-device" ]]; then
  printf 'DEVICE=ready\n'
  exit 0
fi

step() {
  printf '\n>>> %s\n' "$1"
  read -r -p '[Enter when done] ' _
}
capture() {
  local variable="$1" answer
  read -r -p "$2 [y/n]: " answer
  printf -v "$variable" '%s' "$answer"
}

step 'Open ComfyGallery in Quest. Use one controller: aim at the outer Library frame, hold the SIDE GRIP, then move it sideways, closer and farther. The panel should face you while grabbed.'
capture LIBRARY_MOVE 'Did the Library follow and remain in place after release?'
step 'Turn your head away from the original forward direction. Open Library > Position > Bring here. Then try Face me, Closer/Farther, and Left/Right/Up/Down.'
capture PLACEMENT 'Did the Library come in front of your current view, face you, and respond to position controls?'
step 'Drag a Library corner to change its width/height. Scroll near the grid bottom.'
capture LIBRARY_RESIZE 'Did the window resize and the grid reflow?'
capture AUTO_PAGING 'Did the next media page appear without Load more (assuming more ready media exists)?'
step 'Open an ordinary VIDEO. Move the media using its outer frame with the side grip, then resize it using a corner. Also try Position / Size > Smaller and Larger.'
capture PLAYER_MOVE 'Did media and controls move together?'
capture PLAYER_RESIZE 'Did media resize while controls stayed readable at the same physical size below it?'
step 'With the Viewer still enlarged, switch to another video, then an image, then a video. Use Reset layout while facing another direction.'
capture REPLACEMENT 'Did new videos keep the chosen size, and did reset place both panels around your current viewpoint?'
step 'Repeat the movement with the other controller. Try a thumbnail and playback button to check normal selection still works.'
capture INPUT 'Did both controllers and normal selection work?'

printf '\nLIBRARY_MOVE=%s\nPLACEMENT=%s\nLIBRARY_RESIZE=%s\nAUTO_PAGING=%s\nPLAYER_MOVE=%s\nPLAYER_RESIZE=%s\nREPLACEMENT=%s\nINPUT=%s\n' \
  "$LIBRARY_MOVE" "$PLACEMENT" "$LIBRARY_RESIZE" "$AUTO_PAGING" "$PLAYER_MOVE" "$PLAYER_RESIZE" "$REPLACEMENT" "$INPUT"
for answer in "$LIBRARY_MOVE" "$PLACEMENT" "$LIBRARY_RESIZE" "$AUTO_PAGING" "$PLAYER_MOVE" "$PLAYER_RESIZE" "$REPLACEMENT" "$INPUT"; do
  if [[ "$answer" != y && "$answer" != Y ]]; then
    printf 'RESULT=failed\n'
    exit 1
  fi
done
printf 'RESULT=passed\n'
