from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from comfy_gallery_core.db.models import (
    Criterion,
    CriterionVersion,
    EvaluationTemplate,
    EvaluationTemplateItem,
)


@dataclass(frozen=True, slots=True)
class CriterionSeed:
    key: str
    module: str
    media_kind: str
    label: str
    guidance: str
    anchor_0: str
    anchor_5: str
    anchor_10: str


CRITERIA = (
    CriterionSeed(
        "core.aesthetic_appeal",
        "core",
        "any",
        "Aesthetic appeal",
        "Judge the overall visual appeal and usefulness of the result.",
        "Unappealing or unusable",
        "Mixed or ordinary appeal",
        "Exceptionally compelling",
    ),
    CriterionSeed(
        "core.composition",
        "core",
        "any",
        "Composition",
        "Judge framing, balance, hierarchy, and placement.",
        "Failed or chaotic framing",
        "Readable with noticeable issues",
        "Deliberate and highly effective",
    ),
    CriterionSeed(
        "core.prompt_adherence",
        "core",
        "any",
        "Prompt adherence",
        "Judge how well the visible result fulfills the exact prompt.",
        "Misses or contradicts the central request",
        "Captures the main idea but misses important details",
        "Strongly fulfills the explicit intent",
    ),
    CriterionSeed(
        "core.logical_plausibility",
        "core",
        "any",
        "Logical plausibility",
        "Judge internal consistency within the intended visual style.",
        "Fundamentally incoherent",
        "Understandable with notable logic problems",
        "Internally consistent within the intended style",
    ),
    CriterionSeed(
        "core.technical_execution",
        "core",
        "any",
        "Technical execution",
        "Judge visible control, finish, clarity, and degradation.",
        "Severely degraded",
        "Serviceable with visible quality issues",
        "Highly controlled and well finished",
    ),
    CriterionSeed(
        "core.artifact_cleanliness",
        "core",
        "any",
        "Artifact cleanliness",
        "Higher means fewer visible AI-generation defects.",
        "Dominated by generation defects",
        "Some noticeable localized artifacts",
        "No meaningful visible defects",
    ),
    CriterionSeed(
        "video.temporal_consistency",
        "video",
        "video",
        "Temporal consistency",
        "Judge stability across frames, including identity and texture drift.",
        "Persistent flicker or identity collapse",
        "Mostly stable with noticeable drift",
        "Consistently stable",
    ),
    CriterionSeed(
        "video.motion_quality",
        "video",
        "video",
        "Motion quality",
        "Judge whether the intended motion is natural and controlled.",
        "Broken or unusable motion",
        "Recognizable but stiff or irregular",
        "Smooth, natural, and purposeful",
    ),
    CriterionSeed(
        "video.sequence_coherence",
        "video",
        "video",
        "Sequence coherence",
        "Judge whether action and scene progression remain understandable.",
        "Inexplicable progression",
        "Readable action with discontinuities",
        "Logically continuous progression",
    ),
    CriterionSeed(
        "character.identity_fidelity",
        "character",
        "any",
        "Identity fidelity",
        "Judge whether the intended character identity is recognizable.",
        "Target identity is unrecognizable",
        "Partial resemblance",
        "Strongly matches defining traits",
    ),
    CriterionSeed(
        "character.identity_adaptability",
        "character",
        "any",
        "Identity adaptability",
        "Judge whether requested variation succeeds without losing identity.",
        "Variation destroys identity or is ignored",
        "Partial balance",
        "Requested variation succeeds while identity remains intact",
    ),
)


def catalog_id(value: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"comfy-gallery:{value}")


async def ensure_evaluation_catalog(session: AsyncSession) -> None:
    if await session.scalar(select(EvaluationTemplate.id).limit(1)) is not None:
        return
    for seed in CRITERIA:
        criterion = Criterion(
            id=catalog_id(f"criterion:{seed.key}"),
            stable_key=seed.key,
            module=seed.module,
            media_kind=seed.media_kind,
            active=True,
        )
        session.add(criterion)
        session.add(
            CriterionVersion(
                id=catalog_id(f"criterion-version:{seed.key}:1"),
                criterion_id=criterion.id,
                version=1,
                label=seed.label,
                guidance=seed.guidance,
                anchor_0=seed.anchor_0,
                anchor_5=seed.anchor_5,
                anchor_10=seed.anchor_10,
            )
        )
    await session.flush()

    template_specs = (
        ("image.core", "Image core V1", "image", "core", {"core"}),
        ("video.core", "Video core V1", "video", "core", {"core", "video"}),
        ("image.character", "Image character V1", "image", "character", {"character"}),
        ("video.character", "Video character V1", "video", "character", {"character"}),
    )
    for stable_key, name, media_kind, module, included_modules in template_specs:
        template = EvaluationTemplate(
            id=catalog_id(f"template:{stable_key}:1"),
            stable_key=stable_key,
            version=1,
            name=name,
            media_kind=media_kind,
            module=module,
            locked=True,
        )
        session.add(template)
        await session.flush()
        matching = [seed for seed in CRITERIA if seed.module in included_modules]
        session.add_all(
            [
                EvaluationTemplateItem(
                    template_id=template.id,
                    criterion_version_id=catalog_id(f"criterion-version:{criterion.key}:1"),
                    ordinal=ordinal,
                    required=True,
                    allow_na=True,
                )
                for ordinal, criterion in enumerate(matching)
            ]
        )
    await session.flush()


async def get_template(
    session: AsyncSession,
    *,
    media_kind: str,
    module: str,
) -> EvaluationTemplate:
    template = await session.scalar(
        select(EvaluationTemplate)
        .options(
            selectinload(EvaluationTemplate.items)
            .selectinload(EvaluationTemplateItem.criterion_version)
            .selectinload(CriterionVersion.criterion)
        )
        .where(
            EvaluationTemplate.media_kind == media_kind,
            EvaluationTemplate.module == module,
            EvaluationTemplate.locked.is_(True),
        )
        .order_by(EvaluationTemplate.version.desc())
        .limit(1)
    )
    if template is None:
        raise RuntimeError(f"Missing {media_kind}/{module} evaluation template.")
    return template
