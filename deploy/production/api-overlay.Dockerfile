ARG BASE_IMAGE=ccr.ccs.tencentyun.com/travel_agent/travel_agent:api-20260917-reviewedat1
FROM ${BASE_IMAGE}

# Network-constrained release fallback: retain the immutable, lockfile-built
# runtime and replace only application-owned files in a locally built layer.
USER root
COPY --chown=appuser:appuser src /app/src
COPY --chown=appuser:appuser data/governance /app/data/governance
USER appuser
