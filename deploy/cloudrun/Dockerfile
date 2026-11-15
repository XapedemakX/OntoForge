# OntoForge pour Google Cloud Run : UN seul conteneur, FastAPI sert l'API et le front compilé.
# Contexte de build = racine du dépôt :
#   docker build -f deploy/cloudrun/Dockerfile -t ontoforge .                                   # avec Java + HermiT (défaut depuis L32)
#   docker build -f deploy/cloudrun/Dockerfile --build-arg WITH_REASONER=0 -t ontoforge:slim .   # variante légère, sans raisonneur
#
# Pourquoi pas nginx + uvicorn dans le même conteneur ? Cloud Run exécute un seul processus principal : il faudrait un
# superviseur (supervisord, s6) pour en tenir deux, ce qui ajoute une image plus lourde, un point de panne et des journaux mêlés.
# Le front est une SPA de 3 Mo servie à une poignée de visiteurs de démonstration : uvicorn (+ gzip) suffit, et l'authentification,
# les en-têtes de sécurité et le repli SPA vivent au même endroit que l'API. nginx reste utile en local (docker-compose.yml).

# L39-secu : construction reproductible (SEC-14) — npm ci strict, dépendances Python aux versions exactes de backend/constraints.txt,
# images de base par étiquette (digest sha256 À VÉRIFIER : voir docs/guide/contribuer.md « Épingler les images ») ; exécution sans
# privilèges (SEC-11) ; confiance aux en-têtes Forwarded limitée (SEC-16) ; liste d'egress exigée (SEC-16).
#
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
# Utilisateur sans privilèges (SEC-11). Montage Cloud Storage de /data : l'option de montage uid=10001,gid=10001 (ou équivalent) est
# nécessaire pour que cet utilisateur puisse écrire — À VÉRIFIER dans la doc Google avant le premier déploiement.
RUN useradd --system --create-home --uid 10001 --shell /usr/sbin/nologin ontoforge
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app/backend
COPY backend/pyproject.toml ./
COPY backend/ontoforge ./ontoforge
COPY backend/constraints.txt ./
RUN if [ "$WITH_REASONER" = "1" ]; then pip install -c constraints.txt ".[reasoner]"; else pip install -c constraints.txt .; fi
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
    ONTOFORGE_SECRET_FILE=/tmp/ontoforge-master.key \
    PORT=8080
EXPOSE 8080
USER ontoforge
# Cloud Run fournit $PORT ; --proxy-headers pour le schéma https et l'IP du client derrière le frontal de Google.
# FORWARDED_ALLOW_IPS : adresses des frontaux dont les en-têtes X-Forwarded-* sont crus par uvicorn (127.0.0.1 par défaut : aucun, sûr).
# OntoForge lit lui-même X-Forwarded-For à la position du dernier saut de confiance (ONTOFORGE_PROXY_HOPS=1), donc il fonctionne sans
# que uvicorn les réécrive. Ne mettez « * » que si le service n'est joignable QUE par le frontal Google (plage exacte : À VÉRIFIER).
# ONTOFORGE_EGRESS_ALLOW est EXIGÉE en mode public : liste des hôtes joignables par les appels sortants (fournisseur LLM, endpoints SPARQL),
# par exemple « api.anthropic.com,sparql.exemple.org ». Sans elle, le conteneur refuse de démarrer.
CMD ["sh", "-c", ": \"${ONTOFORGE_EGRESS_ALLOW:?ONTOFORGE_EGRESS_ALLOW est requise en mode public (hotes joignables par les appels sortants, separes par des virgules)}\"; exec python -m uvicorn ontoforge.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips=\"${FORWARDED_ALLOW_IPS:-127.0.0.1}\" --no-server-header"]
