FROM postgres:17-alpine@sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193

ARG ALPINE_MIRROR=https://dl-cdn.alpinelinux.org/alpine

RUN sed -i "s|https://dl-cdn.alpinelinux.org/alpine|${ALPINE_MIRROR%/}|g" \
        /etc/apk/repositories && \
    apk update && \
    apk upgrade && \
    apk add su-exec && \
    sed -i 's/exec gosu postgres/exec su-exec postgres/' \
        /usr/local/bin/docker-entrypoint.sh && \
    grep -q 'exec su-exec postgres' /usr/local/bin/docker-entrypoint.sh && \
    rm /usr/local/bin/gosu && \
    rm -rf /var/cache/apk/*

ARG CG_PROJECT_VERSION=0.1.0-rc.6

LABEL org.opencontainers.image.title="Project Comfy Gallery database" \
    org.opencontainers.image.version="$CG_PROJECT_VERSION"
