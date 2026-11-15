# Contexte de build = racine du dépôt (cf. docker-compose.yml) : l'image reproduit l'arborescence
# /app/backend + /app/samples, si bien que samples.py et tests/conftest.py trouvent samples/ sans configuration.
# Image de base : étiquette python:3.12-slim ; digest sha256 À VÉRIFIER (SEC-14, voir docs/guide/contribuer.md « Épingler les images »).
FROM python:3.12-slim
# Java pour le raisonneur OWL 2 DL optionnel (HermiT via owlready2)
RUN apt-get update && apt-get install -y --no-install-recommends default-jre-headless && rm -rf /var/lib/apt/lists/*
# Utilisateur sans privilèges (SEC-11) ; /data (projets, réglages) et /keys (clé maître, SEC-13) lui appartiennent, avant VOLUME,
# pour que les volumes nommés neufs héritent de ces droits.
RUN useradd --system --create-home --uid 10001 --shell /usr/sbin/nologin ontoforge \
 && mkdir -p /data /keys && chown ontoforge:ontoforge /data /keys && chmod 700 /keys
WORKDIR /app/backend
COPY backend/pyproject.toml backend/constraints.txt ./
COPY backend/ontoforge ./ontoforge
# Dépendances installées aux versions exactes de constraints.txt (reproductible, aucune version changée).
RUN pip install --no-cache-dir -c constraints.txt ".[reasoner]"
COPY backend/tests ./tests
COPY samples /app/samples
ENV ONTOFORGE_DATA=/data \
    ONTOFORGE_SAMPLES=/app/samples
VOLUME /data
EXPOSE 8000
USER ontoforge
CMD ["uvicorn", "ontoforge.main:app", "--host", "0.0.0.0", "--port", "8000"]
