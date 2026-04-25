# Backend: FastAPI + Owlready2 + Pellet (JVM через подпроцесс).
# bookworm (Debian 12): у trixie/13 в slim-варианте периодически недоступны зеркала
FROM python:3.12-slim-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends default-jre-headless procps \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/src ./backend/src
COPY onto ./onto

ENV PYTHONPATH=/app/backend/src \
    PYTHONUNBUFFERED=1 \
    ONTOLOGY_FILE_PATH=/app/onto/ontologies/edu_ontology_with_rules.owl \
    REDIS_URL=redis://redis:6379/0

EXPOSE 8000

WORKDIR /app/backend/src
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
