# syntax=docker/dockerfile:1.7

FROM node:24-alpine@sha256:a0b9bf06e4e6193cf7a0f58816cc935ff8c2a908f81e6f1a95432d679c54fbfd AS build

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"

RUN corepack enable

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN --mount=type=cache,target=/pnpm/store,sharing=locked \
    --mount=type=cache,target=/root/.cache/node/corepack,sharing=locked \
    pnpm config set store-dir /pnpm/store && \
    pnpm install --frozen-lockfile

COPY apps/web apps/web
RUN pnpm --filter @comfy-gallery/web build

FROM nginx:1.29-alpine@sha256:5616878291a2eed594aee8db4dade5878cf7edcb475e59193904b198d9b830de

ARG ALPINE_MIRROR=https://dl-cdn.alpinelinux.org/alpine

RUN sed -i "s|https://dl-cdn.alpinelinux.org/alpine|${ALPINE_MIRROR%/}|g" \
        /etc/apk/repositories && \
    apk upgrade --no-cache

COPY deploy/docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/web/dist /usr/share/nginx/html

ARG CG_PROJECT_VERSION=0.1.0-rc.17
ARG CG_SOURCE_URL=https://github.com/blkot/ProjectComfyGallery
ARG CG_REVISION=unknown

LABEL org.opencontainers.image.title="Project Comfy Gallery web" \
    org.opencontainers.image.version="$CG_PROJECT_VERSION" \
    org.opencontainers.image.source="$CG_SOURCE_URL" \
    org.opencontainers.image.revision="$CG_REVISION"

EXPOSE 8080
