# =============================================================================
# Our Little Space — Production Dockerfile for Render
# Django + Daphne backend only
# Frontend is deployed separately as a Render Static Site.
# =============================================================================

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 
    PYTHONUNBUFFERED=1 
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app/backend

# System dependencies for PostgreSQL drivers and Pillow
RUN apt-get update 
    && apt-get install -y --no-install-recommends 
        build-essential 
        libpq-dev 
        libjpeg62-turbo-dev 
        zlib1g-dev 
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir --upgrade pip 
    && pip install --no-cache-dir -r requirements.txt

# Copy Django project
COPY backend/ ./

# Collect Django static files during the image build
RUN python manage.py collectstatic --noinput

# Render supplies PORT automatically
EXPOSE 8000

CMD ["sh", "start.sh"]