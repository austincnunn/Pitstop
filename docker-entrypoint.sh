#!/bin/bash
set -e

# Fix ownership of data directory for bind mounts
# This runs as root before dropping to the 'pitstop' user
if [ -d "/app/data" ]; then
    chown -R pitstop:pitstop /app/data
fi

# Create uploads directory if it doesn't exist
mkdir -p /app/data/uploads
chown -R pitstop:pitstop /app/data

# Migrate the SQLite database file from the old default filename (Willman) to
# the new one (Pitstop) if this is an existing deployment upgrading in place.
if [ -f "/app/data/willman.db" ] && [ ! -f "/app/data/pitstop.db" ]; then
    echo "Renaming existing database willman.db -> pitstop.db..."
    mv /app/data/willman.db /app/data/pitstop.db
    chown pitstop:pitstop /app/data/pitstop.db
fi

# Generate SECRET_KEY on first launch and persist it
KEY_FILE=/app/data/.secret_key
if [ ! -f "$KEY_FILE" ]; then
    echo "Generating new SECRET_KEY..."
    python3 -c "import secrets; print(secrets.token_hex(32))" > "$KEY_FILE"
    chmod 600 "$KEY_FILE"
    chown pitstop:pitstop "$KEY_FILE"
fi
export SECRET_KEY=$(cat "$KEY_FILE")

# Run database migrations as the pitstop user
gosu pitstop flask db upgrade 2>/dev/null || true

# Drop to 'pitstop' user and run the application
exec gosu pitstop "$@"
