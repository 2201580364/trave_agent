FROM node:22.20.0-bookworm-slim AS build
WORKDIR /app
ARG H5_ASSET_VERSION
COPY frontend/package*.json ./
RUN npm ci --legacy-peer-deps
COPY frontend ./
RUN H5_ASSET_VERSION="$H5_ASSET_VERSION" npm run build:h5:release
FROM caddy:2.9.1-alpine
COPY --from=build /app/dist /srv/user
RUN test -s /srv/user/.release-asset-version
RUN printf '%s\n' ':80 {' '    root * /srv/user' '    try_files {path} /index.html' '    file_server' '}' > /etc/caddy/Caddyfile
