# ADR-0015: On-Demand NSFW Image Classification

**Status:** Accepted
**Date:** 2026-11-08

## Context

ComfyGallery needs model suggestions for newly uploaded images and a manual
backfill path, while the J4125 NAS must remain responsive during ordinary
Library browsing. The existing `content_rating` is a human-owned `sfw` / `nsfw`
field. A model result cannot safely overwrite that decision.

## Decision

- Persist classification work as normal PostgreSQL `Job` rows and use Redis /
  Dramatiq only for delivery. Give it a dedicated `nsfw` queue and one-thread
  consumer.
- Keep model inference in an internal CPU-only runtime container separate from
  the API and normal backend image.
- Keep a small runtime supervisor available, but spawn the PyTorch inference
  server as a child process only on the first job. Stop that child after a
  configurable idle timeout. Do not mount the Docker socket into CG.
- Automatically enqueue only ready images after upload, and only when both
  `CG_NSFW_CLASSIFIER_ENABLED` and `CG_NSFW_AUTO_CLASSIFY` are enabled.
- Let users trigger selected Library scopes and individual images. Read-only
  media browsing/status checks never invoke inference.
- Persist the latest output, model ID/revision, class scores, and Review state in
  `media_safety_assessment`. Keep it independent from `Media.content_rating`.
- Start with Viddexa NSFW Detection 2 Mini. Leave NudeNet and a dedicated Nudity
  rating for a later measured phase.

## Consequences

- Idle model memory is released by terminating the process that owns PyTorch and
  the model weights; the supervisor and queue consumer remain as low-memory
  processes.
- The first request after idle pays model startup time. Jobs remain durable while
  that startup happens.
- Original image bytes cross the internal Compose network from the existing
  managed storage volume to the runtime container.
- The runtime image is larger to build and publish than the existing backend
  image, but PyTorch is not added to API or general worker memory.
- Accuracy thresholds and J4125 latency/RAM remain unverified until measured.

## Alternatives considered

- **Load the model in the API process:** mixes CPU-heavy inference with request
  handling and makes normal API memory depend on model loading.
- **Install PyTorch in every backend worker:** increases the size and dependency
  surface of unrelated containers and complicates low-memory accounting.
- **Use Docker socket access to start and stop the runtime container:** gives a
  privileged container control over the Docker host. A child process provides
  the required memory release without that host-level capability.
- **Run NudeNet for every image immediately:** doubles first-stage inference and
  combines two distinct signals before target-library accuracy is known.
