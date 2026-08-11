# Spatial Video AAC Conformance

**Scope:** Local QuickTime Spatial Video (`.mov`) played by AVFoundation and
RealityKit on visionOS

**Research date:** 2026-08-11

**Source policy:** Primary Apple specifications, documentation, and developer
videos

## Conclusion

An AAC-LC, two-channel stereo track sampled at 32 kHz is not disallowed by
Apple's Spatial Video Profile. Apple does not require a 48 kHz audio track,
Spatial Audio, APAC, an audio channel-layout atom, or spatial-audio metadata for
an ordinary rectilinear Spatial Video movie.

Therefore, changing these files from 32 kHz to 48 kHz is a useful compatibility
experiment and a sensible production default, but it is not a standards-required
fix. Full conformance still depends on the AAC sample description, elementary
stream descriptor, channel-count agreement, track enable/volume state, timing,
and the separate MV-HEVC spatial-video signaling.

## What Apple's Spatial Video profile requires

Apple defines a Spatial Video file as a QuickTime movie containing a stereo
MV-HEVC video track and spatial metadata. The Spatial Video Profile constrains
the video track and its `vexu`, stereo-eye, baseline, disparity, projection, and
horizontal-field-of-view signaling; its requirements do not prescribe an audio
codec, sample rate, channel layout, or audio metadata.

Apple's broader spatial-media file-format specification says that ISOBMFF movies
may contain any supported audio format and explicitly declines to prescribe the
audio encoding used for a spatial experience. The extensions also apply to the
QuickTime File Format.

Apple provides further positive evidence that ordinary AAC belongs in this
workflow:

- The MV-HEVC AVFoundation export presets produce movies containing MV-HEVC video
  and AAC audio.
- Apple's HLS Spatial Video example is labeled **Spatial 3D MV-HEVC AAC**.
- Apple's guidance for 3D delivery says the same audio used for 2D delivery can
  be used for 3D delivery.
- Apple-captured movies may carry a stereo AAC track as the fallback for a
  Spatial Audio track. A Spatial Audio companion track is optional, not a
  condition for stereo-video playback.

Primary sources:

- [Creating spatial photos and videos with spatial metadata](https://developer.apple.com/documentation/imageio/creating-spatial-photos-and-videos-with-spatial-metadata)
- [Apple Movie Profiles, Spatial Video Profile](https://developer.apple.com/av-foundation/Apple-Movie-Profiles.pdf)
- [QuickTime and ISO Base Media File Formats and Spatial and Immersive Media, Spatial Audio](https://developer.apple.com/av-foundation/Stereo-Video-ISOBMFF-Extensions.pdf)
- [`AVAssetExportPresetMVHEVC960x960`](https://developer.apple.com/documentation/avfoundation/avassetexportpresetmvhevc960x960)
- [Apple HLS streaming examples](https://developer.apple.com/streaming/examples/)
- [Deliver video content for spatial experiences — WWDC23](https://developer.apple.com/videos/play/wwdc2023/10071/)
- [TN3177: Understanding alternate audio track groups in movie files](https://developer.apple.com/documentation/technotes/tn3177-understanding-alternate-audio-track-groups-in-movie-files)

## Assessment of AAC-LC stereo at 32 kHz

| Property | Apple requirement or evidence | Assessment |
|---|---|---|
| AAC-LC | Apple identifies AAC-LC as a supported stereo codec and its MV-HEVC export presets use AAC. | Conforming codec choice. |
| Two channels | Apple describes stereo AAC as a compatible fallback and uses AAC for ordinary Spatial Video. | Conforming channel count. |
| 32 kHz | The Spatial Video Profile sets no audio sample rate. Apple's archived compatibility guidance supports AAC-LC stereo up to 48 kHz, while current HLS preparation guidance says rates are *normally* 44.1 or 48 kHz. | Not prohibited. 48 kHz is conventional and worth using as a workaround, but is not mandated for a local Spatial Video movie. |
| `chan` atom | QuickTime documents the audio channel-layout atom as optional. | Its absence is not a conformance failure for stereo. If present, it must agree with the two-channel sample description. |
| Spatial Audio/APAC | Not required by the Spatial Video Profile. | Ordinary stereo AAC is sufficient. |

Apple's QuickTime sample-rate field can represent integer sample rates below
`2^16`; 32,000 is within that range. This fact alone does not validate an AAC
bitstream, but it rules out a QuickTime field-range violation.

Primary sources:

- [HLS FAQ: AAC-LC stereo up to 48 kHz](https://developer.apple.com/library/archive/documentation/NetworkingInternet/Conceptual/StreamingMediaGuide/FrequentlyAskedQuestions/FrequentlyAskedQuestions.html)
- [Preparing audio for HTTP Live Streaming](https://developer.apple.com/documentation/http-live-streaming/preparing-audio-for-http-live-streaming)
- [QuickTime sound sample rate](https://developer.apple.com/documentation/quicktime-file-format/sound_sample_description_version_1/sample_rate)
- [QuickTime audio channel layout atom](https://developer.apple.com/documentation/quicktime-file-format/audio_channel_layout_atom)

## QuickTime AAC details that still need validation

Passing an FFmpeg probe as `aac`, `stereo`, and `32000 Hz` does not by itself prove
that the sound track is authored exactly as Apple's player expects. Validate the
following on the final `.mov`:

1. The sound sample entry uses QuickTime type `mp4a` and identifies AAC-LC
   AudioObjectType `2`.
2. The required MPEG-4 elementary sound stream descriptor (`esds`) is present and
   its AudioSpecificConfig agrees with the sample description: AAC-LC, 32,000 Hz,
   and two channels.
3. If the file uses the documented QuickTime `wave` / `siDecompressionParam`
   structure, its contained `esds` is valid; Apple's QuickTime documentation
   strongly recommends a `frma` atom there.
4. The audio track is enabled, self-contained, playable, and selected for audible
   media. If alternate audio tracks exist, at most one track in the alternate
   group is enabled.
5. The track's preferred volume is not zero. Apple documents `1.0` as normal and
   the default for audio written by `AVAssetWriterInput`.
6. Audio samples cover the intended movie time range and are not hidden by an
   edit list or shifted wholly outside the playable interval.
7. A present `chan` layout and every reported channel count agree. The `chan` atom
   itself is optional for stereo.

Primary sources:

- [QuickTime sound sample data: MPEG-4 audio](https://developer.apple.com/documentation/quicktime-file-format/sound_sample_data)
- [QuickTime MPEG-4 audio codec feature](https://developer.apple.com/documentation/quicktime-file-format/mpeg-4_audio_codec)
- [MPEG-4 elementary sound stream descriptor atom](https://developer.apple.com/documentation/quicktime-file-format/mpeg-4_elementary_sound_stream_descriptor_atom)
- [`siDecompressionParam` (`wave`) atom](https://developer.apple.com/documentation/quicktime-file-format/sidecompressionparam_atom)
- [`AVAssetTrack` format, enabled, playable, and volume properties](https://developer.apple.com/documentation/avfoundation/avassettrack)
- [`AVAssetWriterInput.preferredVolume`](https://developer.apple.com/documentation/avfoundation/avassetwriterinput/preferredvolume)

## Confirmed failure in the current `ml-sharp-spatial` mux

The AAC bitstream is valid. The failure is the form of its QuickTime audio
sample entry in the final spatial movie.

The current pipeline creates an intermediate named
`<output>.mvhevc.tmp.mp4`, imports audio with MP4Box's default audio sample-entry
mode, and then merely forces the major brand to `qt  `. Because the output name
still ends in `.mp4`, GPAC 2.4 does not run its automatic whole-file QuickTime
compliance adjustment. It writes an ISO/MPEG-style version-0 `mp4a` entry with
direct `esds` and `btrt` children. Apple AVFoundation does not expose or decode
that audio track when it appears in these otherwise valid spatial QuickTime
movies.

This was isolated with the two Gallery samples as follows:

| Controlled file | AAC payload | MV-HEVC samples and spatial boxes | Audio sample entry | Apple `AVAssetReader` |
|---|---|---|---|---|
| Current output | Original 32 kHz AAC-LC stereo | Original | MPEG version 0, direct `esds` | Fails (`-11829` / `-12848`) |
| Audio extracted to `.m4a` by stream copy | Byte-for-byte AAC copy | Not applicable | Fresh Apple-compatible entry | Passes |
| Full FFmpeg stream-copy remux | Byte-for-byte AAC copy | Remuxed | QuickTime-style entry | Passes, but FFmpeg changes the strict Apple spatial-box hierarchy |
| `chan` atom added only | Original | Original | Original entry plus `chan` | Fails |
| Only the audio `stsd` entry replaced | Original | Original, unchanged | QuickTime-style entry | Passes for both samples |
| GPAC 2.4 production-shaped mux with `asemode=v1-qt` | Original | Preserved | QuickTime v1 `mp4a` with `wave` / `frma` / `esds` | Passes |

The sample-entry-only files continue to pass the project's strict `vexu`,
`hvcC`, `lhvC`, signed-`ctts`, and Apple spatial-box hierarchy validator. This
rules out the spatial metadata injector, AAC sample rate, missing `chan`, and AAC
packet contents as causes.

### Required converter change

Use GPAC's explicit QuickTime Sound Sample Description Version 1 mode when the
audio track is added:

```python
command.extend(["-add", f"{input_sbs}#audio:asemode=v1-qt"])
```

This is preferable to relying on the output extension to make GPAC infer
QuickTime mode. GPAC 2.4 documents `asemode=v1-qt` for this purpose, and its
implementation constructs the QuickTime `wave` structure with `frma`, codec
configuration, endian marker, and terminator.

The converter should also gain a regression assertion that an audio-bearing
output has a QuickTime version-1 `mp4a` sample entry containing `wave`, `frma`,
and `esds`; checking only that FFprobe reports an audio stream allowed this bug
through. On an Apple CI host, an `AVAssetReaderTrackOutput` PCM-decode smoke test
is the authoritative compatibility check.

Primary implementation sources:

- [GPAC 2.4 MP4Box `asemode` option](https://github.com/gpac/gpac/blob/v2.4.0/applications/mp4box/mp4box.c#L904-L909)
- [GPAC 2.4 `v1-qt` option parsing](https://github.com/gpac/gpac/blob/v2.4.0/applications/mp4box/fileimport.c#L1217-L1227)
- [GPAC 2.4 QuickTime audio sample-entry writer](https://github.com/gpac/gpac/blob/v2.4.0/src/isomedia/isom_write.c#L2320-L2495)
- [`ml-sharp-spatial` mux code](https://github.com/blkot/ml-sharp-spatial/blob/main/spatial_video.py#L858-L885)

## RealityKit implication

`VideoPlayerComponent` uses an `AVPlayer`; Apple publishes no additional AAC
profile, rate, layout, or Spatial Audio requirement for this component. The
failure of the same files to produce sound in Apple's RealityKit sample is thus
evidence of a file-muxing or RealityKit/visionOS playback-path compatibility issue,
not evidence that 32 kHz violates the Spatial Video profile.

No XR application audio workaround is warranted. Regenerate spatial variants
with a QuickTime-compatible audio sample description, then let RealityKit's
`VideoPlayerComponent` and `AVPlayer` play the normal audio track.

## Physical-device acceptance

After the converter began importing audio with `asemode=v1-qt`, an existing
Gallery spatial variant was replaced with the repaired movie. Physical Apple
Vision Pro testing confirmed that the XR app presents the variant spatially and
plays its embedded AAC audio correctly. This validates the converter fix and the
app's shared RealityKit/AVPlayer path together; no XR-specific audio substitution
is required.

## Do not apply Apple Immersive Video requirements here

Apple Immersive Video is a separate distribution profile. Apple Immersive Video
Utility expects immersive MV-HEVC plus AIME metadata and normally imports ASAF
audio for APAC output. The Utility can accept embedded stereo AAC for a single
file, but transcodes it to APAC. Those AIME, ASAF, APAC, high-resolution, and
high-frame-rate requirements do not apply to this app's ordinary rectilinear
Spatial Video variants.

Source:

- [Requirements for Apple Immersive Video Utility](https://support.apple.com/guide/immersive-video-utility/requirements-dev4579429f0/web)
