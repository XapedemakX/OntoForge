# OntoForge pour Google Cloud Run : UN seul conteneur, FastAPI sert l'API et le front compilé.
# Contexte de build = racine du dépôt :
#   docker build -f deploy/cloudrun/Dockerfile -t ontoforge .                                   # avec Java + HermiT (défaut depuis L32)
#   docker build -f deploy/cloudrun/Dockerfile --build-arg WITH_REASONER=0 -t ontoforge:slim .   # variante légère, sans raisonneur
#
# Pourquoi pas nginx + uvicorn dans le même conteneur ? Cloud Run exécute un seul processus principal : il faudrait un
# superviseur (supervisord, s6) pour en tenir deux, ce qui ajoute une image plus lourde, un point de panne et des journaux mêlés.
# Le front est une SPA de 3 Mo servie à une poignée de visiteurs de démonstration : uvicorn (+ gzip) suffit, et l'authentification,
# les en-têtes de sécurité et le repli SPA vivent au même endroit que l'API. nginx reste utile en local (docker-compose.yml).

# ---- 1. front compilé -------------------------------------------------------------------------------------------
FROM node:22-alpine AS front
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# documentation embarquée (L28) : import Vite ../../../docs/guide/*.md et ../../../backend/…/help_map.json, relatifs à /app/src/lib
COPY docs/guide /docs/guide
COPY backend/ontoforge/assistant/help_map.json /backend/ontoforge/assistant/help_map.json
RUN npm run build

# ---- 2. exécution ------------------------------------------------------------------------------------------------
FROM python:3.12-slim AS runtime
# WITH_REASONER=1 (défaut depuis L32) ajoute Java (default-jre-headless) et owlready2 pour le raisonneur OWL 2 DL HermiT :
# environ 290 Mo de plus (image ~ 3x plus lourde que la variante légère ; démarrage à froid un peu plus long). Le bouton « Raisonner avec HermiT »
# en dépend. Avec --build-arg WITH_REASONER=0 l'image reste légère : la conformité (W01-W07, profils OWL 2) fonctionne et
# POST /reason répond 501 avec la marche à suivre. Plafonds (variables d'environnement) : ONTOFORGE_HERMIT_TIMEOUT (30 s),
# ONTOFORGE_HERMIT_MAX_TIMEOUT (300 s), ONTOFORGE_HERMIT_MAX_MB (1024 Mo de tas Java), ONTOFORGE_HERMIT_SLOTS (2 calculs en parallèle).
ARG WITH_REASONER=1
RUN if [ "$WITH_REASONER" = "1" ]; then \
      apt-get update && apt-get install -y --no-install-recommends default-jre-headless && rm -rf /var/lib/apt/lists/*; \
    fi
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app/backend
COPY backend/pyproject.toml ./
COPY backend/ontoforge ./ontoforge
RUN if [ "$WITH_REASONER" = "1" ]; then pip install ".[reasoner]"; else pip install .; fi
COPY samples /app/samples
COPY --from=front /app/dist /app/static

# Aucune clé, aucun mot de passe dans l'image : tout vient de l'environnement (Secret Manager sur Cloud Run).
# /data = bucket Cloud Storage monté en volume (projets, réglages) ; le triplestore local vit sur le disque de l'instance (/tmp).
ENV ONTOFORGE_DATA=/data \
    ONTOFORGE_SAMPLES=/app/samples \
    ONTOFORGE_STATIC_DIR=/app/static \
    ONTOFORGE_LOCAL_STORE_DIR=/tmp/ontoforge-triplestore \
    ONTOFORGE_PUBLIC=1 \
    ONTOFORGE_AUTH=password \
    ONTOFORGE_LLM_PROVIDER=mock \
    PORT=8080
EXPOSE 8080
# Cloud Run fournit $PORT ; --proxy-headers pour le schéma https et l'IP du client derrière le frontal de Google.
CMD ["sh", "-c", "exec python -m uvicorn ontoforge.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*' --no-server-header"]
