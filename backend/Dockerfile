# Contexte de build = racine du dépôt (cf. docker-compose.yml) : l'image reproduit l'arborescence
# /app/backend + /app/samples, si bien que samples.py et tests/conftest.py trouvent samples/ sans configuration.
FROM python:3.12-slim
# Java pour le raisonneur OWL 2 DL optionnel (HermiT via owlready2)
RUN apt-get update && apt-get install -y --no-install-recommends default-jre-headless && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/pyproject.toml ./
COPY backend/ontoforge ./ontoforge
RUN pip install --no-cache-dir ".[reasoner]"
COPY backend/tests ./tests
COPY samples /app/samples
ENV ONTOFORGE_DATA=/data \
    ONTOFORGE_SAMPLES=/app/samples
VOLUME /data
EXPOSE 8000
CMD ["uvicorn", "ontoforge.main:app", "--host", "0.0.0.0", "--port", "8000"]
