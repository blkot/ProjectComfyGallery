FROM ghcr.io/astral-sh/uv:python3.13-alpine@sha256:48fb7780491d06b7a8705341808536c2c20356c85d7a100858998038a11703f3

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apk update && \
    apk upgrade && \
    apk add ffmpeg su-exec && \
    rm -rf /var/cache/apk/*

RUN addgroup -S -g 10001 comfy && \
    adduser -S -D -H -u 10001 -G comfy -s /sbin/nologin comfy

COPY --chown=comfy:comfy pyproject.toml uv.lock .python-version ./
COPY --chown=comfy:comfy apps/api/pyproject.toml apps/api/pyproject.toml
COPY --chown=comfy:comfy apps/worker/pyproject.toml apps/worker/pyproject.toml
COPY --chown=comfy:comfy packages/py/core/pyproject.toml packages/py/core/pyproject.toml

RUN uv sync --frozen --no-dev --all-packages --no-install-workspace

COPY --chown=comfy:comfy apps/api apps/api
COPY --chown=comfy:comfy apps/worker apps/worker
COPY --chown=comfy:comfy packages/py/core packages/py/core
COPY --chown=comfy:comfy deploy/docker/api-entrypoint.sh deploy/docker/api-entrypoint.sh
COPY --chown=comfy:comfy deploy/docker/container-entrypoint.sh deploy/docker/container-entrypoint.sh

RUN uv sync --frozen --no-dev --all-packages

ARG CG_PROJECT_VERSION=0.1.0-rc.6

LABEL org.opencontainers.image.title="Project Comfy Gallery backend" \
    org.opencontainers.image.version="$CG_PROJECT_VERSION"

EXPOSE 8000

ENTRYPOINT ["sh", "/app/deploy/docker/container-entrypoint.sh"]

CMD ["uvicorn", "comfy_gallery_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
