# Contexte de construction : la racine du dépôt (docker-compose.yml : context: ., dockerfile: frontend/Dockerfile),
# car le front embarque docs/guide/*.md et backend/ontoforge/assistant/help_map.json (L28).
# Reproductibilité (L39-secu, SEC-14) : `npm ci` seul, sans repli sur `npm install` (le verrou package-lock.json fait foi ; s'il est
# en désaccord avec package.json, la construction échoue). Images de base : étiquettes de version mineure ; digest sha256 À VÉRIFIER
# (voir docs/guide/contribuer.md, « Épingler les images ») — aucun accès réseau n'a permis de le déterminer.
FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY docs/guide /docs/guide
COPY backend/ontoforge/assistant/help_map.json /backend/ontoforge/assistant/help_map.json
RUN npm run build
# nginx SANS privilèges (SEC-11) : processus maître et workers non root, écoute sur 8080. Image nginxinc/nginx-unprivileged, branche 1.27 : À VÉRIFIER
# (existence de l'étiquette 1.27-alpine, état de support de la branche).
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY frontend/security-headers.conf /etc/nginx/ontoforge-security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
