# Product Vision and Principles

**Status:** Accepted
**Working name:** Project Comfy Gallery

## Problem statement

ComfyUI-generated media usually retains enough embedded workflow information to explain how it was produced, but that information is difficult to browse, compare, and remember across hundreds or thousands of outputs. Filenames and directories do not provide stable identity, workflows vary significantly, model roles differ by architecture, and historical model files may later be renamed or deleted.

The user also needs more than a gallery. Manually scored media should become a structured observational dataset that can reveal tendencies such as:

- Which Krea 2 second-pass checkpoint is associated with stronger results?
- Which Wan 2.2 high/low checkpoint pair has a favorable quality profile?
- Which step in a locally trained character LoRA series best preserves identity?
- Does a LoRA behave differently across checkpoints or in combination with other LoRAs?
- Which configurations are associated with artifacts, weak physical logic, or poor prompt adherence?

The application must preserve subjective judgments accurately while making their aggregation reproducible and statistically informative.

## Product vision

Build a self-hosted, single-user ComfyUI media intelligence system that:

1. Preserves original media and embedded workflow metadata as ground truth.
2. Converts heterogeneous workflows into inspectable graph and semantic records.
3. Maintains durable checkpoint, LoRA, node, and historical-reference registries.
4. Provides a fast, interruption-friendly manual review experience.
5. Produces transparent observational analysis of checkpoint and LoRA tendencies.

## Primary user and environment

- One expert ComfyUI user.
- Existing library ranging from hundreds to tens of thousands of media files.
- Images are generally a few megabytes; videos vary by codec but commonly use MP4.
- Application runs through Docker on an x86 NAS with an Intel J4125 CPU and no CUDA GPU.
- The application is accessible on a trusted local network but still requires authentication.
- One or more historical ComfyUI installations may have produced the media, but the application does not identify or manage those instances.

## Product principles

### Ground truth is immutable

Original media bytes and embedded metadata are preserved. Extraction, inference, registry matching, and manual correction are versioned overlays and never rewrite the source evidence.

### Manual work must not be wasted

Evaluation scores are valuable and expensive to reproduce. Criteria changes, migrations, weight changes, reprocessing, and corrections must preserve historical work.

### Unknown is a valid state

An unknown node, model, role, codec, or malformed metadata block must not prevent media import. Unknown and ambiguous information remains visible, correctable, and traceable.

### Identity is not a filename

Media receives an internal UUID. Exact files are identified by SHA-256. Original filenames and paths are provenance only and may collide.

### Parsing is layered

The system separates:

1. Original embedded metadata.
2. Generic graph structure.
3. Versioned semantic observations.
4. Evaluation and analytical interpretation.

### Analysis describes tendencies, not universal winners

Reports describe associations within user-selected media. They show coverage, uncertainty, distributions, and co-occurrence context without claiming laboratory-grade causality.

### Offline operation is normal

ComfyUI, LoRA Manager, and Civitai are enrichment sources. The core library, review, and existing parsing data remain usable when those services are unavailable.

### The NAS is a constrained machine

Background work is bounded, retryable, and observable. Video transcoding is serialized or tightly limited. No MVP feature assumes a GPU.

## Success outcomes

The MVP succeeds when the user can:

- Import a historical NAS library without babysitting individual files.
- Find every media item through stable identity and rich filters.
- Inspect preserved raw workflow data and normalized checkpoint/LoRA usage.
- Correct an inferred node or model mapping once and reprocess affected media.
- Review media across multiple days without losing progress.
- Analyze checkpoint and LoRA tendencies with transparent evidence.
- Restore all metadata and evaluations after a database failure or migration.

## Long-term direction

Later phases may add a ComfyUI custom-node ingestion API, richer rule authoring, Hugging Face enrichment, visual-similarity search, and downstream workflow/configuration retrieval. These extensions must build on the MVP’s stable identities and versioned ground truth rather than bypassing them.
