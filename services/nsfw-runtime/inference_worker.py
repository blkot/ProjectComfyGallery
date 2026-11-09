from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from nsfw_classifier import ClassifierConfig, ClassifierError, NsfwClassifier

settings = ClassifierConfig.from_environment()
classifier = NsfwClassifier(settings)
app = FastAPI(title="Comfy Gallery NSFW Inference Worker")


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "model_id": settings.model_id,
        "model_revision": settings.model_revision,
        "inference_backend": settings.inference_backend,
        "nudity_detector_enabled": settings.nudenet_enabled,
        "nudity_model_revision": (
            settings.nudenet_model_revision if settings.nudenet_enabled else None
        ),
    }


@app.post("/classify")
async def classify(request: Request) -> dict[str, object]:
    image_bytes = await request.body()
    try:
        return await run_in_threadpool(classifier.classify, image_bytes)
    except ClassifierError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
