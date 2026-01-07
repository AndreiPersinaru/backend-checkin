# Backend Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy project
COPY . /app/

# Collect static files
RUN python manage.py collectstatic --noinput || true

# Start server on port 8000 (migrations run via release_command in fly.toml)
# Bind to [::] to support both IPv4 and IPv6 (required for Fly.io proxy)
CMD gunicorn config.wsgi:application --bind [::]:8000 --workers 2 --timeout 30 --access-logfile - --error-logfile -
