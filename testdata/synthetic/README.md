# Synthetic media-container fixtures

`ffmpeg-extended-proj.mov.b64` contains only the MP4/QuickTime container header
from a generated Apple spatial-video sample. The media-data (`mdat`) payload was
removed, so the fixture contains no playable frames, audio, prompt, workflow, or
user filename.

The retained `proj` box has a valid 28-byte payload containing the additional
projection child that FFmpeg 8.0.1 rejected and FFmpeg 8.1 accepts. The backend
Docker build decodes this fixture and requires `ffprobe` to inspect it
successfully. This makes the runtime parser compatibility a release-time
contract without committing the private full spatial video.
