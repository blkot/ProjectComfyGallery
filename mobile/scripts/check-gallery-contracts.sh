#!/bin/zsh
set -euo pipefail
script_dir="${0:A:h}"
mobile_dir="${script_dir:h}"
build_dir="$(mktemp -d /tmp/comfy-gallery-contracts.XXXXXX)"
xcrun swiftc -swift-version 6 -module-cache-path "$build_dir/module-cache" \
  "$mobile_dir"/ComfyGalleryMobile/Core/API/Models/*.swift \
  "$mobile_dir/ComfyGalleryMobile/Core/API/Endpoint.swift" \
  "$mobile_dir/ComfyGalleryMobile/Features/Library/LibraryLayout.swift" \
  "$mobile_dir/ComfyGalleryMobile/Features/Library/MediaDaySection.swift" \
  "$mobile_dir/ComfyGalleryMobile/Core/Media/ViewerPreloadPolicy.swift" \
  "$script_dir/check-gallery-contracts.swift" -o "$build_dir/check-gallery-contracts"
"$build_dir/check-gallery-contracts"
