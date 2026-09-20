# Quest UI and controller design

**Status:** 0.3.0 corrects video scaling and adds visible placement controls after
the user reported 0.2.0 windows resize but video and panel placement do not work.
The revised native interaction remains pending device verification.

## Scene structure

The baseline is one focused passthrough scene containing a Library panel and at
most one Viewer panel. Connect is a transient panel. Library sits near the Viewer
so navigation requires little head movement; controls remain below the media.
Use a visible reset-layout action to recover misplaced panels.

If the user prefers Home multitasking, revise the scene shell to Android panel
activities/hybrid mode while keeping the same data and UI state. Do not promise
visionOS Shared Space behavior, window persistence, or wall snapping on Quest.
The [research](../doc/research/quest-3-development-research.md) documents that distinction.

## Connect and Library

Connect exposes a one-button private build default when configured, plus manual
Gallery URL, masked token entry, Connect, and clear progress/error states. Reuse the existing web-created token contract. Test actual in-headset text
entry in Q2; any future device-code/pairing flow needs its own backend scope.

Library shows a media-first thumbnail grid with All/Images/Videos, Favorite-only,
newest/oldest order, Refresh, and connection state. Retain the XR 2:3 thumbnail
frame as a starting visual treatment; selected media always uses aspect-fit.
Load the next server page automatically within 12 items of the viewport end.
Keep scroll position during paging and show inline Retry at the grid tail.
A batch of four pages with no new ready items pauses automatic scanning, with
a Continue searching action. This avoids an endless scan or error retry loop. A spatial badge means a stored variant exists, not that the
Quest player has been proven to support it.

Empty scope, initial loading, paging, offline cache, failed preview, and expired
authentication have distinct states. Do not display workflow/prompt/model details
in the initial visual browsing flow.

## Viewer

Use one clean media surface and a stable control strip:

```text
[Previous] [Play/Pause] [Next] [Seek] [Loop] [Mute/Volume] [Favorite] [Close]
                         [Auto Play] [Play Spatial / Play in 2D when supported]
```

Adapt controls to content: images have no video seek/audio controls. Show the
poster/loading state immediately; only the active video may auto-play. Keep the
current selection fixed when the Library filter changes; reopening from the grid
captures the new scope. A small scope label makes that behavior clear.

Loop defaults on for the session and survives item changes. Preserve play/pause
intent and time position during representation changes where supported. Closing
the Viewer stops auto-play, cancels pending selection work, and releases its
surface/player. Newer selections own their callbacks; late work cannot overwrite
or tear down the current surface.

Use a recoverable nonmodal message for spatial fallback. An available but unproven
variant must not be advertised as working stereo. Silent source files are allowed;
the app does not invent or separately synchronize missing audio.

## Proposed controller map

| Input/context | Action |
| --- | --- |
| Either controller ray + trigger | Select a thumbnail or activate a control. |
| Trigger held on seek/slider | Drag the focused control. |
| Stick vertical while Library focused | Scroll. |
| Stick horizontal while Viewer focused | Previous/Next, with threshold and repeat debounce. |
| Grip on a panel handle | Move panel; resizing has a visible handle/control. |
| B/Y where platform mapping allows | Back/close; visible alternatives remain. |
| Meta system button | System-owned; no app override. |

The 0.3.0 revision configures `IsdkGrabbable` in Billboard mode so dragged panels
face the viewer, with a wider grab region outside and in front of the content.
Library corners use Relayout mode so the adaptive grid can gain columns/rows.
The media frame uses aspect-preserving Simple resize. `TransformParent` inherits
pose only with `TickTransformSystem.applyScale=false`: the video explicitly
receives the frame's scale, including when a new video is opened at an existing
size. Controls have scale 1 and move below the scaled frame. The previous
counter-scale formula incorrectly assumed inherited scale.

Library's **Position** and the Viewer's **Position / Size** expose Bring here,
Face me, Closer/Farther and four directional buttons. Viewer also has
Smaller/Larger. Placement and reset use the current head pose rather than fixed
world-axis orientation. Bring here places a single panel in front of the head;
Face me only rotates it. Panels remain in place after each action. Initial
placement waits for local head tracking and focused activity. Reset retains
Library dimensions and restores Viewer scale. These actions use normal trigger
clicks and provide a path independent of native grabbing.

Default sizes in meters: Library 1.8 × 1.65; media frame 2.8 × 1.68; controls
1.9 × 0.34. Header/filter space is reduced and the controller-friendly paging
buttons only scroll; fetching is automatic. Volume and Loop move into Options.
Stick shortcuts and B/Y routing are still pending.

References: [Meta panel interaction](https://developers.meta.com/horizon/documentation/spatial-sdk/spatial-sdk-isdk-panels/)
and [SDK 0.14 panel handles](https://developers.meta.com/horizon/reference/spatial-sdk/v0.14.0/com_meta_spatial_isdk_isdkpanelgrabhandle/).
The SDK docs and compiled 0.14.0 APIs were checked. The missing video scale and
incorrect controls offset were identified in code; the controls regression test
failed before correction. The original native movement failure has not been
reproduced by the agent with physical input, so grab configuration remains a
prepared interaction revision, not a hardware-verified root-cause claim.
All mappings are subject to physical-device validation. Support either hand
without requiring simultaneous two-controller gestures. Give one interaction
owner to an active drag and route shortcuts only to the focused panel, preventing
a single press from both clicking and navigating. Pointer hover and pressed
feedback should be unambiguous. Optional haptics may confirm an action.

Disable sample locomotion behaviors that conflict with gallery sticks. No
teleportation, snap turning, walking, or head-locked panels are required.
Controller disconnect/loss of tracking pauses active manipulation safely.

## Comfort and validation

Test label readability, target spacing, media aspect ratio, controller ray
stability, scrolling, one-hand reach, and neck movement on Quest. Provide reset
layout and explicit scale controls. Adapt placement to recenter events rather
than persisting an unvalidated world transform across rooms.

Visual references come from [XR UI design](../XR/spatial-ui-ux-design.md).
Reuse hierarchy, loading states, uncluttered media, and navigation semantics.
Replace Apple-specific points, glass, gaze/pinch, window bars, and RealityKit
effects with tested Quest treatments.
