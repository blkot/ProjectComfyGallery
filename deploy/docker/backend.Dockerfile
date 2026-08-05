# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:0.12.0@sha256:606e70c71c852d03f611b1e56a195d08648507018a7057fab82c4974c4eae105 AS uv

FROM python:3.13-alpine3.24@sha256:399babc8b49529dabfd9c922f2b5eea81d611e4512e3ed250d75bd2e7683f4b0

COPY --from=uv /uv /uvx /bin/

ARG ALPINE_MIRROR=https://dl-cdn.alpinelinux.org/alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY testdata/synthetic/ffmpeg-extended-proj.mov.b64 /tmp/ffmpeg-extended-proj.mov.b64

RUN sed -i "s|https://dl-cdn.alpinelinux.org/alpine|${ALPINE_MIRROR%/}|g" \
        /etc/apk/repositories && \
    apk update && \
    apk upgrade && \
    apk add ffmpeg su-exec && \
    base64 -d /tmp/ffmpeg-extended-proj.mov.b64 > /tmp/ffmpeg-extended-proj.mov && \
    ffprobe -v error -show_format -show_streams -of json \
        /tmp/ffmpeg-extended-proj.mov >/dev/null && \
    ffmpeg -hide_banner -h decoder=hevc 2>&1 | grep -q view_ids_available && \
    rm -f /tmp/ffmpeg-extended-proj.mov /tmp/ffmpeg-extended-proj.mov.b64 && \
    rm -rf /var/cache/apk/*

RUN addgroup -S -g 10001 comfy && \
    adduser -S -D -H -u 10001 -G comfy -s /sbin/nologin comfy

COPY --chown=comfy:comfy pyproject.toml uv.lock .python-version ./
COPY --chown=comfy:comfy apps/api/pyproject.toml apps/api/pyproject.toml
COPY --chown=comfy:comfy apps/worker/pyproject.toml apps/worker/pyproject.toml
COPY --chown=comfy:comfy packages/py/core/pyproject.toml packages/py/core/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --frozen --no-dev --all-packages --no-install-workspace

COPY --chown=comfy:comfy apps/api apps/api
COPY --chown=comfy:comfy apps/worker apps/worker
COPY --chown=comfy:comfy packages/py/core packages/py/core
COPY --chown=comfy:comfy deploy/docker/api-entrypoint.sh deploy/docker/api-entrypoint.sh
COPY --chown=comfy:comfy deploy/docker/container-entrypoint.sh deploy/docker/container-entrypoint.sh

RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --frozen --no-dev --all-packages

ARG CG_PROJECT_VERSION=0.1.0-rc.16
ARG CG_SOURCE_URL=https://github.com/blkot/ProjectComfyGallery
ARG CG_REVISION=unknown

LABEL org.opencontainers.image.title="Project Comfy Gallery backend" \
    org.opencontainers.image.version="$CG_PROJECT_VERSION" \
    org.opencontainers.image.source="$CG_SOURCE_URL" \
    org.opencontainers.image.revision="$CG_REVISION"

EXPOSE 8000

ENTRYPOINT ["sh", "/app/deploy/docker/container-entrypoint.sh"]

CMD ["uvicorn", "comfy_gallery_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
