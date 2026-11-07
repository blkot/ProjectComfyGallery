#!/bin/zsh
set -euo pipefail
script_dir="${0:A:h}"
mobile_dir="${script_dir:h}"
build_dir="$(mktemp -d /tmp/comfy-viewer-regressions.XXXXXX)"
xcrun swiftc -swift-version 6 -module-cache-path "$build_dir/module-cache" \
  "$mobile_dir"/ComfyGalleryMobile/Core/API/Models/*.swift \
  "$mobile_dir/ComfyGalleryMobile/Features/Viewer/ViewerPageWindow.swift" \
  "$mobile_dir/ComfyGalleryMobile/Features/Viewer/ViewerPagingPolicy.swift" \
  "$mobile_dir/ComfyGalleryMobile/Features/Library/LibraryMutationProjection.swift" \
  "$script_dir/check-viewer-regressions.swift" -o "$build_dir/check-viewer-regressions"
"$build_dir/check-viewer-regressions"
