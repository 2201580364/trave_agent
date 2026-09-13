FROM node:22.20.0-bookworm-slim AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci --legacy-peer-deps
COPY frontend ./
RUN npm run build:h5
FROM caddy:2.9.1-alpine
COPY --from=build /app/dist /srv/user
COPY deploy/production/Caddyfile /etc/caddy/Caddyfile
