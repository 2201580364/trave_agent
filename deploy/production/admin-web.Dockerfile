FROM node:22.20.0-bookworm-slim AS build
WORKDIR /app
COPY admin-web/package*.json ./
RUN npm ci
COPY admin-web ./
RUN npm run build
FROM caddy:2.9.1-alpine
COPY --from=build /app/dist /srv/admin
RUN printf '%s\n' ':80 {' '    root * /srv/admin' '    try_files {path} /index.html' '    file_server' '}' > /etc/caddy/Caddyfile
