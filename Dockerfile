# Our Little Space — Django + Daphne backend only

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 
    PYTHONUNBUFFERED=1 
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app/backend

# Install system dependencies
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

# Copy Django backend only
COPY backend/ ./

# Collect Django static files
RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["sh", "start.sh"]