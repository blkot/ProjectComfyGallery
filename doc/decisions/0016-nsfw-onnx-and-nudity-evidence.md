# ADR-0016: ONNX backend and NudeNet evidence

**Status:** Accepted for opt-in implementation; target-NAS acceptance pending
**Date:** 2026-11-08

## Context

ADR-0015 established Viddexa Mini/PyTorch as the initial classification path and
deferred NudeNet until the durable pipeline was in place. The next phases need a
reproducible way to compare ONNX Runtime against PyTorch and to add body-region
evidence without converting detection into a claim about sexual intent.

## Decision

- Keep PyTorch as the default Mini backend and add an opt-in ONNX Runtime FP32
  backend using the same processor config and labels.
- Require local PyTorch/ONNX parity on private sample images before switching the
  NAS backend. Do not default to INT8 or claim a performance win without J4125
  measurements and a human-reviewed accuracy comparison.
- Add NudeNet 320n as a separate optional detector, disabled by default. Its
  default `always` mode favors recall; `risk_or_review` is available as a
  lower-resource option and is explicitly lower recall.
- Store the backend, both model revisions, detector state/mode, raw region
  detections, confidence scores, and boxes with each completed assessment.
- Suggest Nudity only when Mini is confident, its primary label is not Porn or
  Hentai, and a configured exposed-region detection is present. Keep Review when
  Mini is uncertain. Keep human `content_rating` independent.
- Provide ignored local manifests/results and manual-run/parity helpers so the
  user can check each phase against the same private media set.

## Consequences

- ONNX remains a selectable engine, not a guaranteed faster path. The current
  runtime image contains both CPU dependencies; the selected inference backend
  is recorded for every run.
- Enabling NudeNet in `always` mode runs a second inference on every image and
  may increase CPU time. Its detection output does not describe sexual intent
  or reliably prove that detected nudity is nonsexual.
- `risk_or_review` saves CPU but cannot find confident Mini-safe/drawing images
  with NudeNet; users who need higher recall should use `always` and measure it.
- The PyPI `nudenet==3.4.2` page declares MIT, while the current upstream GitHub
  repository lists AGPL-3.0. The exact artifact's distribution terms must be
  checked before publishing a runtime image that contains the package.
- No model weights, private examples, or result files are committed.

## Alternatives considered

- Keep only PyTorch and add no parity path: rejected because J4125 efficiency is
  an explicit deployment concern.
- Treat NudeNet exposed-region labels as a standalone content rating: rejected
  because region detections do not classify sexual intent.
- Run NudeNet only on Mini-sexual predictions by default: rejected as the default
  because it can miss confidently classified safe/drawing images containing
  exposed regions.
- Enable NudeNet automatically for all uploads: rejected until the user
  completes the target-NAS CPU, memory, and accuracy checks.
