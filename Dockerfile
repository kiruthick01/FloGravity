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
# NUMBA_DISABLE_JIT=1 was tried here to fight an earlier OOM crash: it avoids
# numba's LLVM JIT compile-time memory spike, but makes pysheds' conditioning
# routines run as plain Python loops -- ~4.5 minutes for a single route on
# Render's free CPU, unusably slow for a live request. Left at numba's default
# (JIT enabled) now that the real fix -- float32 arrays + freeing pysheds'
# intermediate copies in hydrology.py -- already cuts peak memory ~29% on its
# own; re-test the Render event log for OOM after deploying this if routes
# start failing again, since disabling JIT is still the fallback if needed.

# Cloud Run sets $PORT at runtime (defaults to 8080); shell form so it expands.
CMD ["sh", "-c", "uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
