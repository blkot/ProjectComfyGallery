# Phase 4 Manual Evaluation and Review

**Status:** Implemented and verified on 2026-07-24
**Release:** `0.1.0-rc.4`

## Outcome

Phase 4 adds durable, versioned manual evaluation to the existing media and
workflow-evidence pipeline. A user can organize a review population, score images or
videos without seeing generation configuration, stop after any item, and resume at
the exact saved position later.

The implementation does not require ComfyUI to be online. Review uses the immutable
media, workflow evidence, semantic prompt observations, and cached registries already
stored by earlier phases.

## Database and migration

Alembic revision `0005_manual_evaluation` adds:

- `criterion` and `criterion_version`;
- `evaluation_template` and ordered `evaluation_template_item`;
- `evaluation`, `evaluation_score`, `score_revision`, and
  `evaluation_disposition_revision`;
- `media_collection` and `collection_item`;
- `tag` and `media_tag`;
- `saved_filter`;
- `review_session` and `review_session_item`.

The migration seeds deterministic UUIDv5 identities for 11 criteria and four locked
V1 templates:

| Template | Media | Module | Criteria |
|---|---|---|---:|
| `image.core` V1 | image | core/base | 6 |
| `video.core` V1 | video | core/base | 9 |
| `image.character` V1 | image | optional supplemental | 2 |
| `video.character` V1 | video | optional supplemental | 2 |

Core completion is independent of later supplemental modules. Adding the character
module therefore creates a separate evaluation and does not reopen completed core
work.

Score absence means **Unset**. Stored values are either a scored integer from 0
through 10 or N/A. Database constraints prevent invalid state/value combinations.
Every score change and every Trash/restore action creates an immutable revision row.
Evaluation versions provide optimistic concurrency across browser tabs.

## Backend behavior

The evaluation service owns:

- idempotent evaluation creation from the locked media-type template;
- derived Not started, In progress, and Complete states;
- scored, N/A, Clear, and zero-value handling;
- optimistic version claims and stable conflict errors;
- reversible Trash without changing score progress;
- immutable score/disposition revision history.

The API exposes:

- rubric/template discovery and review summary;
- evaluation list, score, Clear, Trash, restore, and revision endpoints;
- review-session create/list/get/update/delete and item projection endpoints;
- collection, tag, and saved-filter endpoints.

Review session creation supports stable or seeded-random snapshots from:

- direct media selection;
- random eligible media;
- the global In progress pool;
- a validated ad hoc filter;
- a saved filter;
- a static collection;
- a configured source directory.

The review-item response is deliberately narrower than the media-record response. It
contains preview/playback identity, dimensions/duration, exact extracted prompt
observations, criteria, and scores. It omits filenames, source paths, checkpoints,
LoRAs, pipeline patterns, workflow settings, collections, and tags.

## Frontend behavior

### Library management

The Media Library now includes:

- evaluation-state and Trash filters;
- visible Not started, In progress, Complete, and Trash badges;
- explicit card selection;
- start-review-from-selection;
- create-collection-from-selection;
- create-and-apply-tag-to-selection;
- save-current-filter.

### Review home

`/review` shows the global evaluation summary, creates review pools, and lists recent
active sessions with their saved positions and progress. It contains no streak,
deadline, or required-completion mechanics.

### Blind review workspace

`/review/:sessionId` provides:

- a large image viewer or range-capable video player;
- exact prompt text rendered as plain React text;
- a visible “Config hidden” boundary;
- core plus explicitly selected supplemental criteria;
- nullable integer sliders with neutral Unset state;
- distinct zero, N/A, Clear, and Delete/Backspace behavior;
- expandable 0/5/10 anchors;
- autosave only on committed changes rather than every drag event;
- visible saving/error state and one-step local undo;
- reversible Trash;
- explicit Previous/Next and Alt-arrow navigation;
- prefetch of only the next item.

Completing scores, choosing N/A, clearing a score, and changing Trash never navigate.
Opening a session without an explicit `position` query resumes its persisted cursor.

## Verification

### Automated

`make check` passes:

- Ruff lint and formatting: 70 files formatted;
- strict mypy: 51 Python source files;
- pytest: 35 tests;
- Vitest: 7 tests across 2 frontend test files;
- ESLint and TypeScript project checks.

The evaluation regressions cover:

- deterministic V1 catalog and template membership;
- zero versus Unset/N/A;
- all progress-state transitions;
- score and disposition revisions;
- Trash conflict, restore, and score preservation;
- stale-version rejection;
- completed core preservation when character evaluation is added later;
- review-session cursor persistence after an auto-updated timestamp;
- PostgreSQL-safe filtered review-scope SQL;
- review summaries exclude media that is not ready for review;
- URL-position parsing that resumes the stored cursor.

### Migration

A clean PostgreSQL database upgraded through revisions 0001–0005, reported no
Alembic drift, and contained exactly 11 criteria and four templates. A separate
0004→0005 preservation check retained pre-existing user/media rows. Template-evolution
domain coverage demonstrates that completed core scores remain intact when a new
supplemental evaluation is introduced.

### Live Docker/API

The production Compose stack imported all 14 private golden-corpus files (6 images,
8 videos) with zero failures. Live API checks verified:

- all seven review source modes;
- exact-prompt-only blind response shape;
- image core (6 criteria), video core (9), and character supplemental (2);
- score `0`, N/A, Clear, Complete, edit-back-to-In-progress;
- `409 EVALUATION_VERSION_CONFLICT` for a stale write;
- seven score revisions and two Trash disposition revisions in the exercised case;
- no cursor change after scoring or Trash;
- session cursor stop/resume;
- collection, tag, and saved-filter persistence;
- HTTP `206` MP4 byte-range playback.

### Browser

The built web image was exercised through login, dashboard, library, review home,
image review, and video review. The check confirmed:

- saved cursor resumes at item 2 of 2;
- review text contains no checkpoint, LoRA, workflow, source, or filename fields;
- N/A and Clear autosave without movement;
- Trash overlays the same media and restore keeps the same position;
- selection actions enable only when their prerequisites are present;
- video review renders one player and all nine video criteria.

### NAS portability

Fresh backend and frontend images built and loaded successfully for
`linux/amd64`.

## Phase boundary

Phase 4 stores raw judgments only. Weighting profiles, model-factor grouping,
distributions, uncertainty, effect sizes, immutable analysis runs, and drill-down
reports remain Phase 5 work. No winner declaration or prompt-controlled comparison
has been introduced.
