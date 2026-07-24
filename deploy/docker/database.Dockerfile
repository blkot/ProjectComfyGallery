FROM postgres:17-alpine@sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193

RUN apk upgrade --no-cache && \
    apk add --no-cache su-exec && \
    sed -i 's/exec gosu postgres/exec su-exec postgres/' \
        /usr/local/bin/docker-entrypoint.sh && \
    grep -q 'exec su-exec postgres' /usr/local/bin/docker-entrypoint.sh && \
    rm /usr/local/bin/gosu

ARG CG_PROJECT_VERSION=0.1.0-rc.6

LABEL org.opencontainers.image.title="Project Comfy Gallery database" \
    org.opencontainers.image.version="$CG_PROJECT_VERSION"
