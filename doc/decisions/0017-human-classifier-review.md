# ADR-0017: Human Classifier Review and Library Filters

**Status:** Accepted
**Date:** 2026-11-09

## Context

Model output is a suggestion and may be uncertain. A human needs a direct way
to classify both model-flagged images and images that have never been sent to
the classifier. The existing binary `media.content_rating` is already used by
the Library and must remain stable during this classifier rollout.

## Decision

- Persist the latest human classifier rating in a separate
  `media_safety_review` row with rating, reviewer, and timestamp.
- Offer Safe, Sexy, Nudity, and Explicit as human ratings. The rating remains
  independent from both the latest model assessment and `media.content_rating`.
- Resolve the Library's effective `classifier_rating` from the human decision
  first, then the latest completed model suggestion.
- Provide classifier-state filters for Unclassified, Suggested, Needs review,
  Human reviewed, Processing, and Failed. Apply classifier filters to media
  listing, detail navigation, slideshows, saved filters, and filter-backed
  selections.
- Add a temporary Library shortcut that scopes to unclassified images, opens
  the first one, and preserves that scope for detail navigation.

## Consequences

- Human decisions are available even when the classifier is disabled or has
  never processed the image.
- Reclassification does not erase an existing human decision. Clearing the
  human decision reveals the model suggestion again, or returns the item to
  Unclassified when no model assessment exists.
- The old binary `content_rating` remains available until a future migration is
  explicitly planned.
