# ADR-0014: Event-Driven MSS Orchestration

**Status:** Accepted
**Date:** 2026-08-10

## Decision

This ADR supersedes only ADR-0013's long-polling-worker portion. ComfyGallery
creates one durable submission command, streams the original once to MSS, commits
the returned batch ID, and completes that short `Job`. MSS owns GPU FIFO execution
and publishes the completed file through CG's validated variant-import boundary.

CG activation (or duplicate resolution) of the ready spatial variant is the
authoritative, idempotent success event. A bounded, one-GET reconciliation actor
runs at low frequency and on demand to recover missed events, report progress, and
surface generation/publish failures. It never sleeps or watches in a worker.
Transient status-read failures leave the run active and schedule another finite
attempt; they do not reopen or fail the already-completed submission Job.
Publication failures/skips retain the MSS batch and use MSS's publish-only endpoint;
they never regenerate on CG retry. A crash after MSS accepts a request but before
the batch ID commits remains an unavoidable accept-before-commit duplicate window
until MSS supports an idempotency command key.

## Consequences

No NAS spatial worker thread is retained for an hours-long GPU operation. Existing
rc.19 records with a batch finish their obsolete submit Job and reconcile; records
without one recover submission. Returned MSS URLs remain untrusted data: CG uses
only configured-origin `/spatial/batches/{batch_id}` paths.
