# Glossary

## Analysis run

An immutable snapshot of a dataset, score revisions, filters, grouping factor, exclusions, criteria/template versions, weighting profile, and calculated results.

## Architecture family

A broad model architecture boundary such as Wan 2.1, Wan 2.2, or Krea 2. It is not the same as an individual checkpoint file.

## Artifact

A canonical model file identity, preferably established by cryptographic hash. Checkpoints and LoRAs are artifact types.

## Checkpoint

The actual main model file selected in a workflow, including safetensors diffusion models or GGUF variants. This differs from the broader architecture family.

## Checkpoint pair

An ordered combination of checkpoint usages, such as Wan 2.2 high-noise/low-noise or Krea 2 first-pass/second-pass.

## Complete

An evaluation in which every criterion in its snapshotted template is resolved by either a 0–10 score or N/A.

## Composite score

A score calculated from raw criteria through a versioned weighting profile. It is never stored as a replacement for raw scores.

## Embedded ground truth

The unchanged workflow, API prompt, and related metadata read from the original media.

## Evaluation template

A versioned snapshot of the criteria applicable to an evaluation. Later additions do not mutate historical templates.

## Exact duplicate

Two source files whose original bytes have the same SHA-256 hash.

## Historical model reference

A model filename/path preserved from a workflow when no current file or definitive registry artifact is available.

## In progress

An evaluation with at least one resolved criterion and at least one unset criterion.

## LoRA training series

A user-trained family of adapter artifacts that share an opaque name prefix and differ by a parsed numeric training step.

## Managed storage

The application-controlled filesystem area containing immutable original media and generated derivatives.

## Media record

The application entity identified by UUIDv7 that owns workflow data, evaluation history, and source references.

## Model enrichment

Optional provider metadata, such as Civitai information. Enrichment is independent of local identity and availability.

## Model usage

The occurrence of a checkpoint or LoRA reference within one workflow, including pipeline pattern, usage slot, raw value, and confidence.

## N/A

A criterion state meaning the axis cannot reasonably be judged. It counts as resolved but is excluded from numerical aggregation.

## Node definition

The structural schema for a ComfyUI node class: inputs, outputs, datatypes, module, and related metadata.

## Node semantic mapping

A versioned interpretation of a node input as a checkpoint, LoRA, prompt, sampler setting, or another supported feature.

## Not started

An evaluation with no resolved criteria.

## Observational analysis

Analysis describing tendencies and associations in selected historical media without claiming that a factor caused the outcome.

## Pipeline pattern

The structural model-use pattern of a workflow, such as single-model, dual-noise, single-pass, or dual-pass.

## Proxy

A derived browser-compatible video used for preview while the original remains authoritative.

## Review session

A lightweight snapshot of candidate media, ordering, current position, and optional modules. It is resumable but imposes no completion requirement.

## Semantic observation

A versioned, sourced, confidence-bearing fact extracted or corrected from a generic workflow graph.

## Source inventory

Persistent records of files observed under configured import roots, used to make rescans incremental and track moves, deletion, errors, and deduplication.

## Trash

A reversible media-evaluation flag for failed generations. It preserves media, parsing, and scores but excludes them from analysis by default.

## Usage slot

The checkpoint’s position in one workflow, such as single, high-noise, low-noise, first-pass, or second-pass. It is not part of canonical artifact identity.

## Weighting profile

A versioned set of criterion weights used to calculate composite scores from raw evaluation values.
