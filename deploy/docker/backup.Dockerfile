FROM postgres:17-alpine@sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193

ARG ALPINE_MIRROR=https://dl-cdn.alpinelinux.org/alpine

RUN sed -i "s|https://dl-cdn.alpinelinux.org/alpine|${ALPINE_MIRROR%/}|g" \
        /etc/apk/repositories && \
    apk update && \
    apk upgrade && \
    apk add su-exec && \
    rm /usr/local/bin/gosu && \
    rm -rf /var/cache/apk/*

COPY deploy/operations/backup-entrypoint.sh /usr/local/bin/backup-entrypoint
COPY deploy/operations/backup.sh /usr/local/bin/comfy-gallery-backup
COPY deploy/operations/restore.sh /usr/local/bin/comfy-gallery-restore

RUN chmod 0555 \
    /usr/local/bin/backup-entrypoint \
    /usr/local/bin/comfy-gallery-backup \
    /usr/local/bin/comfy-gallery-restore

ARG CG_PROJECT_VERSION=0.1.0-rc.16
ARG CG_SOURCE_URL=https://github.com/blkot/ProjectComfyGallery
ARG CG_REVISION=unknown

LABEL org.opencontainers.image.title="Project Comfy Gallery backup" \
    org.opencontainers.image.version="$CG_PROJECT_VERSION" \
    org.opencontainers.image.source="$CG_SOURCE_URL" \
    org.opencontainers.image.revision="$CG_REVISION"

ENTRYPOINT ["/usr/local/bin/backup-entrypoint"]
CMD ["schedule"]
