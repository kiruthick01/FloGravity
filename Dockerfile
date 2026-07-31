# Backend service (server/) for Render/Cloud Run. Built from the repo root so
# it can COPY the drainage_lcp package alongside server/.
FROM python:3.11-slim

WORKDIR /app

# rasterio's wheel bundles GDAL statically but that bundled GDAL still
# dynamically links a few system libs the slim base image strips out.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libexpat1 \
    libsqlite3-0 \
    && rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt

COPY drainage_lcp/ drainage_lcp/
COPY server/ server/

ENV PYTHONUNBUFFERED=1

# Cloud Run sets $PORT at runtime (defaults to 8080); shell form so it expands.
CMD ["sh", "-c", "uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
