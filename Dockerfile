# Compile Tailwind CSS once at build time instead of in every browser.
# Output is architecture-independent, so build on the native builder platform.
FROM --platform=$BUILDPLATFORM debian:trixie-slim AS css
ARG BUILDARCH
ARG TAILWIND_VERSION=v3.4.17
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && arch=$([ "$BUILDARCH" = "arm64" ] && echo arm64 || echo x64) \
    && curl -fsSL -o /usr/local/bin/tailwindcss \
       "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-${arch}" \
    && chmod +x /usr/local/bin/tailwindcss
WORKDIR /src
COPY tailwind.config.js ./
COPY app/templates ./app/templates
COPY app/static ./app/static
RUN tailwindcss -c tailwind.config.js -i app/static/css/tailwind.input.css -o /tailwind.css --minify

FROM python:3.14-slim-trixie

WORKDIR /app

# Install system dependencies including WeasyPrint requirements and gosu for privilege dropping
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    gir1.2-pango-1.0 \
    gir1.2-gdkpixbuf-2.0 \
    gosu \
    postgresql-common \
    && rm -rf /var/lib/apt/lists/*

# pg_dump for full-database backups. Must match the server's major version
# (postgres:18 in docker-compose.yml); Debian's own package is older, so use
# the official PGDG repo via postgresql-common's helper script.
RUN /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y \
    && apt-get install -y --no-install-recommends postgresql-client-18 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .
COPY --from=css /tailwind.css /app/app/static/css/tailwind.css

# Create non-root user and set up directories
RUN useradd --create-home --shell /bin/bash pitstop \
    && mkdir -p /app/data/uploads \
    && chown -R pitstop:pitstop /app

# Copy and set up entrypoint
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Build args for version info
ARG GIT_SHA=""
ARG BUILD_DATE=""

# Labels for auto-update tools (Watchtower, etc.)
LABEL com.centurylinklabs.watchtower.enable="true"

# Set environment variables
ENV FLASK_APP=run.py
ENV PYTHONUNBUFFERED=1
ENV GIT_SHA=${GIT_SHA}
ENV BUILD_DATE=${BUILD_DATE}

# Expose port
EXPOSE 5151

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD gosu pitstop python -c "import urllib.request; urllib.request.urlopen('http://localhost:5151/health')" || exit 1

# Use entrypoint to fix permissions then run as 'pitstop' user
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["gunicorn", "-c", "gunicorn.conf.py", "--preload", "--bind", "0.0.0.0:5151", "--workers", "2", "--threads", "4", "run:app"]
