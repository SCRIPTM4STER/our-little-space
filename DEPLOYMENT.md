# Deployment Guide — Our Little Space on Railway

This guide walks you through deploying the app to Railway. No prior DevOps experience is required — just follow the steps in order.

## Overview

The app runs as a **single Railway service** that serves both:
- The Django backend API (Daphne ASGI server)
- The React frontend (built with Vite, served by WhiteNoise)

A **Railway PostgreSQL database** is attached as a separate service and connected via the `DATABASE_URL` environment variable.

## Files Created for Deployment

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage Docker build: builds Vite frontend, then runs Django backend |
| `railway.json` | Railway deployment configuration (start command, health check, restart policy) |
| `docker-compose.yml` | Local development parity (optional, for testing locally with Docker) |
| `start.sh` | Container entrypoint: runs migrations, collects static files, starts Daphne |
| `backend/.env.example` | Reference for all backend environment variables |
| `frontend/.env.example` | Reference for frontend environment variables |

## Step 1: Create a Railway Account

1. Go to [https://railway.app](https://railway.app)
2. Sign up with your GitHub account
3. Create a new project: click **"New Project"** → **"Deploy from GitHub repo"**
4. Select the `our-little-space` repository

## Step 2: Add PostgreSQL Database

1. In your Railway project dashboard, click **"New"**
2. Select **"Database"** → **"PostgreSQL"**
3. Railway will provision a managed PostgreSQL instance
4. Once ready, click on the PostgreSQL service → **"Connect"** tab
5. Copy the `DATABASE_URL` connection string (it looks like `postgresql://postgres:xxx@host:5432/railway`)

## Step 3: Connect Database to Backend Service

1. Click on your backend service (the GitHub deployment)
2. Go to the **"Variables"** tab
3. Add these variables manually (do **not** use a DATABASE_URL reference):

| Variable | Where to get it | Example value |
|----------|----------------|---------------|
| `USE_POSTGRESQL` | Set manually | `True` |
| `POSTGRES_DB` | PostgreSQL service → Connect tab | `railway` |
| `POSTGRES_USER` | PostgreSQL service → Connect tab | `postgres` |
| `POSTGRES_PASSWORD` | PostgreSQL service → Connect tab | (the password shown there) |
| `POSTGRES_HOST` | PostgreSQL service → Connect tab | `host.railway.internal` |
| `POSTGRES_PORT` | PostgreSQL service → Connect tab | `5432` |
| `POSTGRES_SSLMODE` | Set manually | `prefer` |

4. Click **"New Variable"** for each one above and enter the value.
5. The backend will automatically use PostgreSQL when `USE_POSTGRESQL=True`.

## Step 4: Set Required Environment Variables

On your backend service **Variables** tab, add the following:

| Variable | Value | Purpose |
|----------|-------|---------|
| `SECRET_KEY` | Generate a random 50+ character string | Django's cryptographic signing key |
| `DEBUG` | `False` | Disables debug mode for production |
| `ALLOWED_HOSTS` | `*.up.railway.app,your-custom-domain.com` | Comma-separated list of allowed hostnames |
| `CORS_ALLOWED_ORIGINS` | `https://your-frontend-domain.com` | Origins allowed to call the API |
| `CSRF_TRUSTED_ORIGINS` | `https://your-frontend-domain.com` | Origins trusted for CSRF cookies |
| `SECURE_SSL_REDIRECT` | `True` | Redirects HTTP to HTTPS |
| `SESSION_COOKIE_SECURE` | `True` | Session cookies only over HTTPS |
| `CSRF_COOKIE_SECURE` | `True` | CSRF cookies only over HTTPS |
| `SECURE_HSTS_SECONDS` | `31536000` | HSTS header (1 year) |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `True` | Apply HSTS to subdomains |
| `SECURE_HSTS_PRELOAD` | `True` | Include in HSTS preload list |
| `SECURE_PROXY_SSL_HEADER` | `HTTP_X_FORWARDED_PROTO,https` | Tells Django Railway's proxy handles HTTPS |
| `LOG_LEVEL` | `INFO` | Application log verbosity |
| `USE_POSTGRESQL` | `True` | Switches from SQLite to PostgreSQL |
| `POSTGRES_DB` | Railway database name | PostgreSQL database name |
| `POSTGRES_USER` | Railway database user | PostgreSQL username |
| `POSTGRES_PASSWORD` | Railway database password | PostgreSQL password |
| `POSTGRES_HOST` | Railway database host | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_SSLMODE` | `prefer` | PostgreSQL SSL mode |

### How to generate SECRET_KEY

Run this locally:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Copy the output and paste it as the `SECRET_KEY` value in Railway.

## Step 5: Add Persistent Storage for Media Uploads

User avatar uploads are stored in `backend/media/`. On Railway, you need a persistent volume so uploads survive redeploys:

1. In your Railway project dashboard, click **"New"**
2. Select **"Volume"**
3. Name it `media-storage`
4. Size: 1 GB (sufficient for avatar images)
5. Click **"Create Volume"**
6. Click on your backend service → **"Volumes"** tab
7. Click **"Add Volume"**
8. Select `media-storage` volume
9. Mount path: `/app/backend/media`

## Step 6: Configure Custom Domain (Optional)

1. Click on your backend service → **"Settings"** → **"Domains"**
2. Click **"Custom Domain"**
3. Enter your domain (e.g., `api.yourdomain.com`)
4. Follow the DNS instructions Railway provides
5. Add the domain to `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` environment variables

## Step 7: Deploy

1. Push your code to GitHub
2. Railway will automatically detect the `railway.json` and Dockerfile
3. The build starts automatically: frontend builds with Vite, backend installs Python dependencies, static files are collected
4. Once deployed, Railway assigns a URL like `https://your-app.railway.app`

## Step 8: Verify Deployment

1. Open your Railway app URL in a browser
2. Visit `https://your-app.railway.app/api/health/` — should return a JSON health response
3. Visit `https://your-app.railway.app/` — should show the React frontend
4. Register a user, log in, and test core features

## Step 9: Run Migrations After First Deploy

The `start.sh` script runs `python manage.py migrate --noinput` automatically on every container start. No manual migration step is needed.

## Environment Variable Reference

### Backend Variables (`backend/.env.example`)

| Variable | Description | Production Value |
|----------|-------------|-----------------|
| `SECRET_KEY` | Django signing key | Random string (generate locally) |
| `DEBUG` | Debug mode | `False` |
| `ALLOWED_HOSTS` | Allowed hostnames | Your Railway domain(s) |
| `DATABASE_URL` | Database connection string | From PostgreSQL service |
| `CORS_ALLOWED_ORIGINS` | CORS allowed origins | Your frontend domain |
| `CSRF_TRUSTED_ORIGINS` | CSRF trusted origins | Your frontend domain |
| `SECURE_SSL_REDIRECT` | Force HTTPS | `True` |
| `SESSION_COOKIE_SECURE` | Secure session cookies | `True` |
| `CSRF_COOKIE_SECURE` | Secure CSRF cookies | `True` |
| `SECURE_HSTS_SECONDS` | HSTS duration | `31536000` |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | HSTS subdomains | `True` |
| `SECURE_HSTS_PRELOAD` | HSTS preload | `True` |
| `SECURE_PROXY_SSL_HEADER` | Proxy SSL header | `HTTP_X_FORWARDED_PROTO,https` |
| `LOG_LEVEL` | Log level | `INFO` |

### Frontend Variables (`frontend/.env.example`)

| Variable | Description | Production Value |
|----------|-------------|-----------------|
| `VITE_API_URL` | Backend API URL | Leave unset (uses same origin) |

## Local Development with Docker

```powershell
# Build and run locally
docker-compose up --build

# The app will be available at http://localhost:8000
```

## What Still Needs to Be Done in the Railway Dashboard

These steps **must** be performed in the Railway web dashboard — they cannot be automated from the repository:

1. **Create the project** — Connect your GitHub repository to Railway
2. **Add PostgreSQL** — Create the database service via Railway dashboard
3. **Link DATABASE_URL** — Reference the PostgreSQL `DATABASE_URL` on your backend service
4. **Set SECRET_KEY** — Generate and add as an environment variable
5. **Set domain variables** — `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` with your actual domain
6. **Add persistent volume** — Create and mount a volume for `/app/backend/media`
7. **Add custom domain** (optional) — Configure DNS through Railway

## Health Check

The health check endpoint is at `/api/health/`. Railway checks this endpoint to confirm the service is healthy. If it returns non-200, Railway will restart the container.

## Rollback

In the Railway dashboard, go to your service → **"Deployments"** → select a previous deployment → **"Rollback"**.

## Security Notes

- `DEBUG` must be `False` in production
- `SECRET_KEY` must be unique and never committed to version control
- All cookies are secure (HTTPS-only) when `SECURE_SSL_REDIRECT=True`
- HSTS is enforced for 1 year after HTTPS is verified
- Media uploads are stored on persistent volume
- The frontend build output is baked into the Docker image at build time