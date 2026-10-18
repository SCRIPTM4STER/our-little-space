# =============================================================================
# Our Little Space — Production Dockerfile for Render
# =============================================================================
# Stage 1: Build the Vite frontend
# =============================================================================
FROM node:24-alpine AS frontend-build
WORKDIR /app/frontend

# Install frontend dependencies
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

# Copy frontend source and build for production
COPY frontend/ .
RUN npm run build

# =============================================================================
# Stage 2: Run the Django backend + serve frontend
# =============================================================================
FROM python:3.13-alpine AS backend
WORKDIR /app/backend

# Install system dependencies needed by Python packages (psycopg, Pillow)
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    jpeg-dev \
    zlib-dev \
    && rm -rf /var/cache/apk/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY backend/ .

# Copy the built frontend from Stage 1 into the backend static directory
# WhiteNoise will serve these assets at / (frontend) and /static/ (Django admin)
COPY --from=frontend-build /app/frontend/dist ./frontend_dist

# Collect Django static files (admin, REST framework, WhiteNoise)
RUN python manage.py collectstatic --noinput --clear

# Render injects $PORT automatically. Daphne listens on that port.
EXPOSE 8000

# Entrypoint: run migrations, then start Daphne ASGI server
CMD ["sh", "/app/backend/start.sh"]