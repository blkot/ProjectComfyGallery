# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:python3.13-alpine3.23@sha256:31a524210097e4f2d6f732d525cf9479c02ec966a0cd13f43ef71650ef3abf72

ARG ALPINE_MIRROR=https://dl-cdn.alpinelinux.org/alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN sed -i "s|https://dl-cdn.alpinelinux.org/alpine|${ALPINE_MIRROR%/}|g" \
        /etc/apk/repositories && \
    apk update && \
    apk upgrade && \
    apk add ffmpeg su-exec && \
    ffmpeg -hide_banner -h decoder=hevc 2>&1 | grep -q view_ids_available && \
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

ARG CG_PROJECT_VERSION=0.1.0-rc.11
ARG CG_SOURCE_URL=https://github.com/blkot/ProjectComfyGallery
ARG CG_REVISION=unknown

LABEL org.opencontainers.image.title="Project Comfy Gallery backend" \
    org.opencontainers.image.version="$CG_PROJECT_VERSION" \
    org.opencontainers.image.source="$CG_SOURCE_URL" \
    org.opencontainers.image.revision="$CG_REVISION"

EXPOSE 8000

ENTRYPOINT ["sh", "/app/deploy/docker/container-entrypoint.sh"]

CMD ["uvicorn", "comfy_gallery_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
