# Backend service (server/) for Cloud Run. Built from the repo root so it can
# COPY the drainage_lcp package alongside server/.
FROM python:3.11-slim

WORKDIR /app

COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt

COPY drainage_lcp/ drainage_lcp/
COPY server/ server/

ENV PYTHONUNBUFFERED=1

# Cloud Run sets $PORT at runtime (defaults to 8080); shell form so it expands.
CMD ["sh", "-c", "uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
