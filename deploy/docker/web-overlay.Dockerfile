ARG BASE_IMAGE
FROM ${BASE_IMAGE}

RUN rm -rf /usr/share/nginx/html && mkdir -p /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY dist/ /usr/share/nginx/html/
RUN find /usr/share/nginx/html -type d -exec chmod 0755 {} + && \
    find /usr/share/nginx/html -type f -exec chmod 0644 {} +

ARG CG_PROJECT_VERSION=0.1.0-rc.17
ARG CG_SOURCE_URL=https://github.com/blkot/ProjectComfyGallery
ARG CG_REVISION=unknown

LABEL org.opencontainers.image.title="Project Comfy Gallery web" \
    org.opencontainers.image.version="$CG_PROJECT_VERSION" \
    org.opencontainers.image.source="$CG_SOURCE_URL" \
    org.opencontainers.image.revision="$CG_REVISION"
