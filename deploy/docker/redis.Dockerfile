FROM redis:8-alpine@sha256:9d317178eceac8454a2284a9e6df2466b93c745529947f0cd42a0fa9609d7005

ARG ALPINE_MIRROR=https://dl-cdn.alpinelinux.org/alpine

RUN sed -i "s|https://dl-cdn.alpinelinux.org/alpine|${ALPINE_MIRROR%/}|g" \
        /etc/apk/repositories && \
    apk upgrade --no-cache

ARG CG_PROJECT_VERSION=0.1.0-rc.6

LABEL org.opencontainers.image.title="Project Comfy Gallery broker" \
    org.opencontainers.image.version="$CG_PROJECT_VERSION"
