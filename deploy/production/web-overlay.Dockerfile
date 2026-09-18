ARG BASE_IMAGE=ccr.ccs.tencentyun.com/travel_agent/travel_agent:h5-20260917-m1a
FROM ${BASE_IMAGE}

# Network-constrained release fallback: static assets were compiled locally
# before this image is built; no source or build toolchain is sent to server.
COPY frontend/dist /srv/user
RUN test -s /srv/user/.release-asset-version
