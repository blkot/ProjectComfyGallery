# Mobile UI/UX Design

**Status:** Implementation-ready interaction specification  
**Design language:** Native iOS, media-first, quiet, interruption-friendly

## Design principles

1. **The media is the interface.** Chrome is subordinate and never covers meaningful
   image/video content.
2. **Blind means blind.** Review exposes prompt and rubric only. Configuration,
   model, workflow, source, and file evidence never leak through labels, menus,
   accessibility text, errors, or debug UI.
3. **One decision at a time.** Controls communicate Unset, N/A, score, pending, and
   saved states without turning review into a forced task.
4. **Leaving is normal.** Stop is always available. There are no streaks, deadlines,
   completion celebrations, or guilt language.
5. **Navigation is deliberate.** Score completion and Trash never change the item.
6. **Native behavior wins.** Use standard navigation, sheets, menus, player controls,
   haptics, typography, safe areas, and accessibility semantics.

## Information architecture

Use a three-tab `TabView`:

```text
Library                    Review                     Settings
├─ Visual grid             ├─ Continue               ├─ Connection
├─ Compact filters         ├─ Start new              ├─ Privacy
└─ Media viewer            ├─ Recent sessions        └─ Cache
                           └─ Review workspace
```

- **Library** is visual browsing without metadata.
- **Review** is the only scoring entry point and preserves the blind boundary.
- **Settings** contains connection/security/cache controls, not media metadata.

On iPad, retain the three product areas but use `NavigationSplitView` where it
improves Library and Review home. Do not force desktop web layouts onto iPad.

## First launch and connection

### Screen

- App mark and product name.
- Server URL field.
- Primary action: **Connect**.
- Secondary action: **Paste API token** or **Sign in to pair this device**.
- Connection status with plain language:
  - Checking server
  - Server found
  - Authentication required
  - Connected
  - Could not connect

Normalize the base URL after validation, but keep the user's scheme and port. Do not
silently upgrade, downgrade, or replace a hostname with an IP address.

For plain HTTP, show a one-time warning that credentials and media are not encrypted
on the LAN. Do not block a user-controlled local deployment.

## Library

### Grid

- Use `LazyVGrid` with adaptive columns.
- Default cell ratio is 2:3.
- Suggested spacing: 8 pt on compact width and 12 pt on regular width.
- Fill the cell with an aspect-fill preview and clip overflow.
- Show only:
  - video glyph for videos;
  - subtle progress ring/dot if desired;
  - reversible Trash veil/icon if applicable.
- Do not show titles, filenames, dimensions, dates, model names, or IDs.
- Preserve scroll position independently for each active filter.
- Load the next page before the user reaches the last visible row.

### Filters

Keep filters intentionally small:

- All / Images / Videos
- All / Not started / In progress / Complete
- Hide Trash / Trash only / Include Trash

Use a compact toolbar button that opens a sheet. The current filter may be used to
create a blind review session through **Review this view**. Do not add checkpoint or
LoRA filters to mobile V1 because they reveal experiment configuration and expand
scope beyond the companion's purpose.

### Empty and error states

- No media: “No media matched this view.”
- Offline with cached items: keep cached cells and show a nonblocking offline bar.
- Offline without cached items: connection explanation and Retry.
- Failed thumbnail: neutral placeholder, video/image glyph, Retry on tap.

## Viewer

Viewer is a full-screen visual pager separate from Review.

- Top safe-area bar: Back and an optional Share-disabled placeholder only if a later
  product decision enables export.
- Bottom safe-area bar: Previous, position, Next.
- Controls live outside the media stage and may auto-hide after inactivity.
- Image behavior:
  - contain by default;
  - double-tap between fit and 1:1;
  - pinch and pan;
  - reset zoom when paging.
- Video behavior:
  - use native playback controls;
  - contain by default;
  - remember mute preference during the current app session;
  - do not auto-play the next item.

No metadata drawer exists in V1.

## Review home

Review home prioritizes continuation over session creation.

### Content order

1. **Continue review** card for the most recently active session.
2. **Resume In progress** action with count.
3. **Start random review** action.
4. Recent sessions list.
5. Less-frequent New Session options.

A session card may show:

- generic name or source kind;
- current position and candidate count;
- Complete and In progress counts;
- last opened time;
- active/finished/abandoned state.

Do not show `scope_snapshot` contents that may contain checkpoint/LoRA filters. A
generic label such as “Filtered library session” is sufficient.

### New session sheet

- Source:
  - Random unevaluated
  - In progress
  - Current Library view, when launched from Library
- Maximum items: stepper or numeric field, default 100, range 1–2000.
- Ordering: Random or Stable.
- Optional rubric: Character identity.
- Primary action: **Start review**.

Collections, saved filters, and source roots may be resumed if the backend session
already exists, but selecting or managing them is outside mobile V1.

## Review workspace

### Compact portrait layout

```text
┌──────────────────────────────┐
│ Stop        18 / 100   Saved │  fixed safe-area header
├──────────────────────────────┤
│                              │
│       image / video          │  fixed media stage, about 48–56% height
│                              │
├──────────────────────────────┤
│ Prompt                    ▾  │
│ Core evaluation              │
│ Aesthetic appeal       [—]   │
│ 0 ───────●──────────── 10    │  independently scrollable
│ [Clear]               [N/A]  │
│ …                            │
├──────────────────────────────┤
│ Previous    Undo       Next  │  fixed bottom safe-area bar
└──────────────────────────────┘
```

- Use `safeAreaInset` for the header and navigation bar.
- The media stage is fixed while rubric content scrolls.
- The exact prompt is the first section. It may collapse after reading, but the app
  must not label it with node names or workflow origin.
- On small screens or very large Dynamic Type, allow the media stage to reduce to a
  documented minimum rather than clipping controls.

### Landscape and iPad

Use a two-column arrangement:

- Media stage on the left, contained within the safe viewport.
- Prompt and criteria in an independently scrollable pane on the right.
- Stop/status belong above the right pane or in the navigation bar.
- Previous/Next remain outside the media.

Use proportional space rather than fixed pixels. A starting split is 58% media and
42% controls, with a minimum control-pane width of approximately 360 pt.

### Prompt

- Show exact extracted prompt fields in server order.
- Open the first field by default.
- Use selectable text.
- Preserve whitespace and do not sanitize, rewrite, truncate semantically, or
  suppress adult language.
- Long prompts collapse visually with an explicit Show More action.
- If no prompt exists, state “No prompt was extracted for this media.”

### Criterion control

Each criterion card contains:

- criterion label;
- current state/value chip;
- brief guidance disclosure;
- integer slider from 0 through 10;
- Clear action;
- N/A action when allowed;
- optional expandable 0/5/10 anchors.

Interaction rules:

- Unset shows an em dash and neutral track, not `0`.
- Tapping or dragging selects the nearest integer.
- Use light selection haptics when the committed integer changes; respect system
  haptic settings and avoid continuous vibration.
- Commit on drag end or direct tap, not on every transient movement.
- Selecting N/A disables the score fill without moving the slider to zero.
- Clear returns to Unset.
- The last acknowledged change may be undone from the fixed navigation bar.
- Disable only the affected criterion during an in-flight request when possible;
  avoid freezing all media/player controls.

### Save state

Use one compact status in the header:

- **Saved** with checkmark.
- **Saving…** with progress indicator.
- **Saved locally** when queued offline.
- **Needs attention** when reconciliation or conflict requires action.

Never claim Saved until the backend response is acknowledged. Do not use modal
success confirmations for ordinary score changes.

### Trash

Place **Mark as Trash** after the rubric, visually separated from scoring. Require a
single deliberate tap but not a confirmation dialog; it is reversible. After
marking:

- keep the same media visible;
- show a clear Trash veil/badge;
- change the action to **Restore from Trash**;
- preserve and continue showing scores.

### Stop and navigation

- **Stop** returns to Review home without changing session status.
- Previous and Next are explicit buttons.
- A horizontal swipe may supplement them, but only when the visible item has no
  unresolved save/conflict state.
- On the last item, Next becomes **Finish session** only as an explicit action.
- Finishing changes session status; completing evaluations alone does not.

If there is a pending command, Stop persists it locally and explains “Saved locally;
will sync when connected.” It must not force the user to remain on screen.

## Conflict UX

When the server returns `EVALUATION_VERSION_CONFLICT`:

1. Stop automatic retries for that evaluation.
2. Fetch the current review item.
3. Present a compact sheet:
   - “This score changed elsewhere.”
   - Server value and this device's intended value.
   - **Use server value**
   - **Reapply my value**
4. Reapply only against the newly fetched version and only after explicit choice.

Do not show configuration metadata in the conflict sheet.

## Loading and prefetch

- Show the media stage immediately with a neutral placeholder.
- Fetch review JSON and media independently.
- Prefetch only the next item's JSON and media after current content is ready.
- Cancel obsolete prefetch when the user changes session or moves backward.
- Never let prefetch delay score writes.
- For videos, show the poster while the authenticated local playback file downloads.

## Visual system

Prefer system tokens:

- `Color(.systemBackground)`, `secondarySystemBackground`, `label`,
  `secondaryLabel`, `separator`, `systemRed`, and `tint`.
- San Francisco system typography with semantic text styles.
- SF Symbols by name, including `photo`, `play.rectangle`, `checkmark.circle`,
  `arrow.left`, `arrow.right`, `trash`, `arrow.uturn.backward`, and `wifi.slash`.
- Rounded rectangles use a restrained 12–16 pt radius.
- Support light and dark appearance from the first build.

Do not encode evaluation state using color alone.

## Accessibility checklist

- VoiceOver reads the media only as “Image under review” or “Video under review”; it
  must not read a filename or identifier.
- Criterion slider accessibility value is “Unset,” “Not applicable,” or
  “N out of 10.”
- Provide adjustable increment/decrement actions.
- Announce Saved, Saved locally, and conflict changes politely, not on every slider
  tick.
- Logical focus order: Stop/status, media/player, prompt, criteria, Trash, navigation.
- Landscape and iPad layouts remain usable with keyboard and Switch Control.
- Respect Reduce Motion for pager transitions and Reduce Transparency for overlays.

## UX validation scenarios

- One-handed portrait scoring.
- Large phone landscape video review.
- iPad split layout.
- Maximum Dynamic Type with the media still reachable.
- VoiceOver scoring from Unset to `0`, N/A, and Clear.
- Background during Saving.
- Network loss during a score and during video download.
- Conflict caused by editing the same item in the web app.
- Trash and completion with proof that no automatic navigation occurs.
- Review item with no prompt, several prompts, and a very long prompt.

