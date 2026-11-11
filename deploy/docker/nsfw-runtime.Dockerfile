FROM ghcr.io/astral-sh/uv:0.12.0@sha256:606e70c71c852d03f611b1e56a195d08648507018a7057fab82c4974c4eae105 AS uv

FROM python:3.11.18-slim-bookworm@sha256:061c190f3d5815b341a18dfe8a45771f8ba68c15a607ea56997fde3009ac4eec

COPY --from=uv /uv /uvx /bin/

ARG CG_PROJECT_VERSION=0.1.0-rc.51
ARG CG_SOURCE_URL=https://github.com/blkot/ProjectComfyGallery
ARG CG_REVISION=unknown

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    OMP_NUM_THREADS=2 \
    MKL_NUM_THREADS=2

WORKDIR /app

RUN useradd --create-home --uid 10002 --shell /usr/sbin/nologin nsfw

COPY services/nsfw-runtime/requirements.txt ./requirements.txt
RUN uv pip install --system "torch>=2.6,<3" --index-url https://download.pytorch.org/whl/cpu && \
    uv pip install --system -r requirements.txt

COPY services/nsfw-runtime/app.py \
    services/nsfw-runtime/inference_worker.py \
    services/nsfw-runtime/nsfw_classifier.py \
    services/nsfw-runtime/benchmark.py ./

RUN chown -R nsfw:nsfw /app

USER 10002:10002

LABEL org.opencontainers.image.title="Project Comfy Gallery NSFW runtime" \
    org.opencontainers.image.version="$CG_PROJECT_VERSION" \
    org.opencontainers.image.source="$CG_SOURCE_URL" \
    org.opencontainers.image.revision="$CG_REVISION"

EXPOSE 8001

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
