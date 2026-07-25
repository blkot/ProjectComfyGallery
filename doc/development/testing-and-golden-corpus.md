# Testing Strategy and Golden Corpus

**Status:** Accepted

The project maintains Python, frontend, compose, migration, and operational
workflow checks in CI; the exact test count grows with each slice. The analytics
slice also has clean PostgreSQL migration/drift, live Docker/API/ComfyUI, browser
interaction, private image/video corpus, and `linux/amd64` image-build evidence
recorded in
[Phase 5 model-focused analytics](phase-5-model-analytics.md).

## Quality strategy

Testing is risk-weighted:

1. Immutable identity/evidence and evaluation preservation receive the strongest automated coverage.
2. Workflow parsing uses representative golden files plus synthetic edge cases.
3. External integrations use captured contract fixtures.
4. Review and analysis use domain, API, and end-to-end tests.
5. NAS resource behavior uses bounded-load tests.

## Test layers

### Unit tests

Cover:

- UUID/hash/source identity rules.
- Path normalization and root containment.
- LoRA series suffix parsing.
- Node schema fingerprinting.
- Semantic-mapping precedence.
- Pipeline-pattern/usage-slot extraction helpers.
- Evaluation state derivation.
- N/A/unset/zero behavior.
- Trash restore behavior.
- Composite calculations.
- Filter validation.
- Statistical calculation helpers.

### Database/domain integration tests

Cover:

- Unique constraints and exact deduplication.
- Transaction rollback/idempotency.
- Source rename/change/missing histories.
- Versioned extraction runs and manual overrides.
- Model-reference resolution precedence.
- Evaluation revisions and optimistic concurrency.
- Saved analysis member/revision snapshots.
- Alembic upgrade from historical fixture databases.

### Worker integration tests

Cover:

- Stage retry/idempotency.
- API/worker restart reconciliation.
- Disk/full-read errors.
- ffprobe/thumbnail/proxy command failures.
- Optional external integration outages.
- Reprocessing fan-out after registry correction.

### API contract tests

Cover:

- Authentication/session/CSRF/token behavior.
- Pagination/filter semantics.
- Idempotency keys.
- Stable error envelopes.
- Media authorization and range requests.
- Optimistic-concurrency conflicts.
- OpenAPI compatibility.

### Frontend component tests

Cover:

- Nullable slider states and keyboard behavior.
- N/A and clear actions.
- No automatic navigation.
- Trash/restore.
- Autosave states and conflict handling.
- Filter chips and saved-filter serialization.
- Confidence/provenance labels.
- Chart coverage/insufficient states.

### End-to-end tests

Representative paths:

1. Login → upload → processing → library → record.
2. Source scan → duplicate/rename/change handling.
3. Unknown node → manual mapping → reprocessing.
4. Model sync with partial Civitai failure.
5. Start review → partial exit → resume → complete → edit.
6. Trash and restore without navigation.
7. Create analysis → save → revise score → rerun.
8. Backup → restore → verify evaluation history.

## Golden corpus purpose

The golden corpus validates real ComfyUI metadata, not just JSON invented by tests. It is required because custom output nodes, versions, and video containers may embed data differently.

The corpus should contain:

- A representative group of images with related but varied workflows.
- A representative group of videos selected similarly.
- Common checkpoint patterns.
- Common LoRA loaders/combinations.
- Local LoRA training-series references.
- At least one unknown/deleted historical model reference if available.
- At least one malformed/no-workflow file, which may be synthetic.

Format diversity is helpful but not required from the user; synthetic fixtures can cover additional formats.

## Corpus timing

The first private corpus was supplied and audited during Phase 2. Future parser or
registry work may request a new case only when an observed metadata carrier,
node-definition variant, or semantic ambiguity is not represented.

## Local layout

```text
testdata/
  golden/
    README.local.md
    images/
      image-<sha256-prefix>/
        original.<ext>
        expected.local.json
        notes.local.md
    videos/
      video-<sha256-prefix>/
        original.<ext>
        expected.local.json
        notes.local.md
  synthetic/
    ...
```

Golden user media remains local/private and is not committed. The repository ignores
private originals and `*.local.*` expectations/notes while allowing sanitized
structural fixtures and documentation.

## Case organization

Each case ID is stable and does not depend on the media filename.

Future local semantic expectations may use `expected.local.json`. Expectations assert
stable facts rather than every incidental JSON field. Phase 3 validates pipeline slots
and canonical/historical model resolution directly against the local database after
live synchronization; private model names and prompts remain outside Git.

The Phase 2 regression currently asserts evidence/graph invariants directly and does
not commit private checkpoint, LoRA, or prompt content.

## User organization request

When requested, the user may place:

- Representative images under `testdata/golden/images/incoming/`.
- Representative videos under `testdata/golden/videos/incoming/`.
- An optional plain-text note describing which files belong to similar workflow families.

The Phase 2 implementation process:

1. Hash and assign stable case IDs.
2. Move files within the workspace into per-case local directories.
3. Inspect metadata without logging raw prompt bodies.
4. Assert carrier, representation, graph, and observation invariants.
5. Resolve architecture/slot expectations through the correctable Phase 3 registry
   and retain genuinely ambiguous values as unresolved.

The first corpus contains 6 PNG images and 8 MP4 videos. Thirteen contain both API
prompt and visual workflow; one is a valid API-prompt-only MP4. Eleven distinct API
graph signatures cover the critical Krea and Wan patterns documented for the project.
Phase 3 resolved this corpus into single-model, dual-noise, single-pass, and dual-pass
patterns and retained four workflow-only historical model references.

## Synthetic fixtures

Committed small fixtures cover:

- PNG/JPEG/WebP metadata variants.
- MP4/WebM container metadata variants.
- Missing/truncated JSON.
- Duplicate filenames with different bytes.
- Same exact bytes under multiple filenames.
- Unknown node definitions.
- Multiple schema variants of one node class.
- Wildcard/dynamic inputs.
- Filename-only model identity ambiguity.
- LoRA series suffix edge cases.
- N/A/missing historical evaluation cases.

Synthetic media should be minimal and license-safe.

## Parser regression policy

For every parser/extractor change:

- Run the entire golden/synthetic suite.
- Compare raw evidence hashes.
- Compare generic graph facts.
- Compare semantic observations and confidence.
- Require intentional expectation updates for changes.
- Preserve old extractor-version outputs in migration/reprocessing tests.

## Statistical tests

Use deterministic seeds for bootstrap tests.

Test:

- Empty/one-item/tiny groups.
- Unequal group sizes.
- All N/A criterion.
- Scores at bounds 0 and 10.
- Shared-criteria intersection across template versions.
- Immutable saved run after source data changes.
- Effect-size and confidence-interval invariants.

Tests should verify formulas and data inclusion, not exact floating-point formatting alone.

## Performance tests

On development hardware and eventually NAS:

- Inventory scan of tens of thousands of synthetic entries.
- Streaming hash memory use.
- Gallery query latency with large metadata tables.
- Reprocessing fan-out.
- Review next-item/prefetch latency.
- Video transcode queue serialization.
- Analytics matrix with sparse groups.

Performance budgets will be calibrated after the initial implementation; regressions require visible benchmarks.

## Security tests

- Malicious prompt HTML/script strings.
- Path traversal and symlink escape.
- MIME/extension spoofing.
- Oversized/deep workflow JSON.
- Unauthorized media and range requests.
- CSRF and session fixation.
- Token storage/revocation.
- Provider response with malicious strings.

## Release quality gate

A release cannot be considered ready when:

- Golden corpus regressions are unexplained.
- Migration/restore test fails.
- Evaluation state transitions fail.
- An accepted requirement has no implementation/test mapping.
- The documentation and traceability matrix are stale.
