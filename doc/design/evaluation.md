# Manual Evaluation System

**Status:** Accepted and implemented in Phase 4

Implementation and verification evidence is recorded in
[Phase 4 manual evaluation and review](../development/phase-4-manual-evaluation.md).

## Purpose

The evaluation system captures deliberate, subjective human judgments as durable structured data. Aggregation can become reproducible and quantitatively useful, but the scores do not become objective ground truth.

## Evaluation philosophy

- Configuration-blind and prompt-aware.
- Fast enough for hundreds of media.
- Safe to stop after any item.
- Nullability is explicit.
- Historical work survives rubric evolution.
- Raw scores remain authoritative.
- Navigation is always user-controlled.

## V1 criterion catalog

Stable IDs are normative. Wording may receive cosmetic clarification without changing the ID; semantic changes require a new criterion or criterion version.

### Universal core

| Stable ID | Criterion | 0 anchor | 5 anchor | 10 anchor |
|---|---|---|---|---|
| `core.aesthetic_appeal` | Aesthetic appeal | Unappealing or unusable | Mixed or ordinary appeal | Exceptionally compelling |
| `core.composition` | Composition | Failed or chaotic framing | Readable with noticeable issues | Deliberate and highly effective |
| `core.prompt_adherence` | Prompt adherence | Misses or contradicts the central request | Captures the main idea but misses important details | Strongly fulfills the explicit intent |
| `core.logical_plausibility` | Logical plausibility | Fundamentally incoherent | Understandable with notable logic problems | Internally consistent within the intended style |
| `core.technical_execution` | Technical execution | Severely degraded | Serviceable with visible quality issues | Highly controlled and well finished |
| `core.artifact_cleanliness` | Artifact cleanliness | Dominated by generation defects | Some noticeable localized artifacts | No meaningful visible defects |

Artifact cleanliness is positively directed: higher means cleaner.

### Video module

| Stable ID | Criterion | 0 anchor | 5 anchor | 10 anchor |
|---|---|---|---|---|
| `video.temporal_consistency` | Temporal consistency | Persistent flicker or identity collapse | Mostly stable with noticeable drift | Consistently stable |
| `video.motion_quality` | Motion quality | Broken or unusable motion | Recognizable but stiff or irregular | Smooth, natural, and purposeful |
| `video.sequence_coherence` | Sequence coherence | Inexplicable progression | Readable action with discontinuities | Logically continuous progression |

Static or low-motion content is not penalized solely for lacking motion. Motion quality considers whether the intended motion works.

### Character module

| Stable ID | Criterion | 0 anchor | 5 anchor | 10 anchor |
|---|---|---|---|---|
| `character.identity_fidelity` | Identity fidelity | Target identity is unrecognizable | Partial resemblance | Strongly matches defining traits |
| `character.identity_adaptability` | Identity adaptability | Variation destroys identity or is ignored | Partial balance | Requested variation succeeds while identity remains intact |

Identity adaptability helps distinguish overtrained/overpowering LoRAs from adaptable identity preservation.

## Criterion value model

For each applicable criterion:

- **Unset:** no evaluation decision; prevents completion.
- **Scored:** integer from 0 through 10.
- **N/A:** cannot reasonably be judged; counts as resolved and is excluded from numerical analysis.

Zero is a real score and is never used for unset, missing, Trash, or N/A.

An optional short N/A reason may be stored. Example: no usable prompt for prompt adherence.

## Templates and modules

### Core selection

- Images use the universal image-applicable core.
- Videos use the universal core plus the video module.

### Optional modules

- Character module is enabled manually for a selected review-session scope.
- Module choice is snapshotted when evaluation begins.
- A later-added module does not reopen an existing completed evaluation.
- Additional criteria/modules can be collected later as a supplemental evaluation.

### Versioning

- Label/help-text fixes that preserve meaning may create a criterion-version update under the stable criterion ID.
- Meaning changes create a new criterion identity/version and template version.
- Adding criteria never marks old completed work incomplete.
- Historical uncollected values remain absent/not-collected, not zero.

## Evaluation states

Derived progress state:

- **Not started:** no criteria resolved.
- **In progress:** at least one resolved and at least one unset.
- **Complete:** every applicable criterion scored or N/A.

Trash is a separate reversible disposition:

- Scores remain stored.
- Analysis excludes the media by default.
- Restoring Trash returns to the state derived from preserved scores.
- Marking or restoring Trash is revisioned.

## Review-session semantics

A review session snapshots:

- Candidate media IDs.
- Stable order or randomization seed.
- Current cursor.
- Source scope description.
- Applicable optional modules.

It does not own the scores. Evaluations are committed independently per media.

The user may:

- Stop at any time.
- Resume later.
- Ignore or abandon a session.
- Delete session state without deleting evaluations.

The global In progress pool exists independently and orders partial evaluations most-recent-first by default.

## Review page information boundary

Visible:

- Large media preview/player.
- Exact extracted prompt fields.
- Criterion controls, guidance, status, and session position.

Hidden during scoring:

- Checkpoint and LoRA names.
- Pipeline pattern and workflow settings.
- Model registry metadata.
- Source directory, collections, and experiment tags.
- Other configuration-revealing metadata.

Filenames have no product significance and are not needed for review.

The normal library and media-record pages expose all metadata.

## Slider interaction contract

Each criterion uses a nullable integer slider:

- Unset: no active fill/value and a visually neutral/hidden thumb.
- Clicking the track sets the nearest integer.
- Dragging snaps to integer values.
- Committed value is displayed numerically.
- A clear control returns the criterion to unset.
- Delete/Backspace clears the focused criterion.
- Zero remains visually distinguishable from unset.
- Undo restores the last local committed change.
- Autosave occurs when the committed value changes, not on every transient drag event.

Anchor guidance:

- 0/5/10 labels are visible through tooltip or expansion.
- Intermediate values are user interpolation.

## Navigation

- No automatic next after a score makes the evaluation Complete.
- No automatic next after marking Trash.
- Next is explicit through button or keyboard action.
- Leaving the page after successful autosave preserves state.
- Prefetching the next media is allowed for speed but does not navigate.

## Autosave and concurrency

Autosave requests should include an optimistic-concurrency version:

- The API rejects stale edits rather than overwriting a newer score.
- The UI surfaces conflicts and offers reload/reapply.
- A successful save returns the authoritative evaluation state/version.

Single-user deployment makes conflicts uncommon, but multiple tabs remain possible.

## Editing completed work

Completed evaluations remain editable:

- Latest score is used by live analysis.
- Every edit records old/new value/state and timestamp.
- Clearing a criterion returns the evaluation to In progress.
- Saved analysis runs continue referencing the historical score revisions they used.
- Live report caches become stale and are recomputed.

## Weighting profiles

- Raw criteria are permanent source data.
- Composite scores are calculated, never baked into evaluation rows.
- Equal weighting is the default.
- Optional profiles contain versioned weights.
- Changing a profile creates a new version and recalculates live/history views without editing raw scores.
- Reports record the profile version used.
- Weight-sensitivity analysis may show whether conclusions change materially under plausible profiles.

## Accessibility and speed

- All controls are keyboard accessible.
- Focus order follows criterion order.
- Color is not the only indication of unset/N/A/score.
- Video controls remain operable while the criteria pane scrolls independently.
- Autosave status is visible but unobtrusive.
- Failed saves remain clearly unsaved and retryable.

## Data-protection invariants

1. No migration converts missing values to zero.
2. No template change deletes scores.
3. No composite overwrites raw criteria.
4. Trash never deletes media or scores.
5. Manual revisions remain auditable.
6. Saved analysis runs retain exact revision references.
