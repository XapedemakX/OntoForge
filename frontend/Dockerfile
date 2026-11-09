# Contexte de construction : la racine du dépôt (docker-compose.yml : context: ., dockerfile: frontend/Dockerfile),
# car le front embarque docs/guide/*.md et backend/ontoforge/assistant/help_map.json (L28).
FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend/ ./
COPY docs/guide /docs/guide
COPY backend/ontoforge/assistant/help_map.json /backend/ontoforge/assistant/help_map.json
RUN npm run build
FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
