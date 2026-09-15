FROM node:22.20.0-bookworm-slim AS build
WORKDIR /app
ARG H5_ASSET_VERSION=ui10
COPY frontend/package*.json ./
RUN npm ci --legacy-peer-deps
COPY frontend ./
RUN npm run build:h5 \
    && sed -i "s#return\"chunk/\"+a+\".js\"#return\"chunk/\"+a+\".js?v=${H5_ASSET_VERSION}\"#; s#return\"css/\"+a+\".css\"#return\"css/\"+a+\".css?v=${H5_ASSET_VERSION}\"#" dist/js/app.js \
    && sed -i "s#/js/232.js#/js/232.js?v=${H5_ASSET_VERSION}#; s#/js/app.js#/js/app.js?v=${H5_ASSET_VERSION}#; s#/css/app.css#/css/app.css?v=${H5_ASSET_VERSION}#" dist/index.html
FROM caddy:2.9.1-alpine
COPY --from=build /app/dist /srv/user
RUN printf '%s\n' ':80 {' '    root * /srv/user' '    try_files {path} /index.html' '    file_server' '}' > /etc/caddy/Caddyfile
