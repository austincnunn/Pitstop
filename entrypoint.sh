#!/bin/sh

KEY_FILE=/app/data/.secret_key

# Generate and save key if it doesn't exist yet
if [ ! -f "$KEY_FILE" ]; then
    echo "Generating new SECRET_KEY..."
    python3 -c "import secrets; print(secrets.token_hex(32))" > "$KEY_FILE"
    chmod 600 "$KEY_FILE"
fi

# Load it into the environment
export SECRET_KEY=$(cat "$KEY_FILE")

# Hand off to your actual app
exec "$@"
