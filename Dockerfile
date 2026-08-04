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
# Confirmed via two real Render deploys, not just local measurement: with JIT
# enabled, even after the float32/gc memory fixes (which measured 301MB peak
# locally, comfortably under the 512MB cap), the instance still OOM-crashed
# in production ("Ran out of memory (used over 512MB)" in the Render event
# log). Local numbers on this arm64 dev machine don't reliably predict
# Render's actual x86_64 container's memory behavior around numba's JIT
# compile spike. Disabling JIT is the only configuration that has actually
# succeeded end-to-end on the real deployment (confirmed HTTP 200 with
# correct route data) -- slow (~4.5 min/request on free-tier CPU), but
# correct and stable. A paid tier with more RAM would be needed to get both
# speed and JIT enabled; not worth it for a portfolio deployment.
ENV NUMBA_DISABLE_JIT=1

# Cloud Run sets $PORT at runtime (defaults to 8080); shell form so it expands.
CMD ["sh", "-c", "uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
