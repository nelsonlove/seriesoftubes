#!/bin/bash
set -e

echo "Starting SeriesOfTubes..."

# Check for .tubes.yaml configuration file
if [ ! -f "/app/.tubes.yaml" ]; then
    echo "ERROR: .tubes.yaml configuration file not found!"
    echo "Please create .tubes.yaml from .tubes.example.yaml and mount it into the container."
    echo "Example: docker run -v $(pwd)/.tubes.yaml:/app/.tubes.yaml ..."
    exit 1
fi


# Wait for PostgreSQL to be ready (if using PostgreSQL)
if [[ "$DATABASE_URL" == postgresql* ]]; then
    echo "Waiting for PostgreSQL..."
    # Extract host and port from DATABASE_URL
    # Format: postgresql://user:pass@host:port/db
    DB_HOST=$(echo $DATABASE_URL | sed -E 's/.*@([^:]+):.*/\1/')
    DB_PORT=$(echo $DATABASE_URL | sed -E 's/.*:([0-9]+)\/.*/\1/')
    
    until nc -z -v -w30 $DB_HOST $DB_PORT 2>/dev/null; do
        echo "Waiting for database connection at $DB_HOST:$DB_PORT..."
        sleep 2
    done
    echo "PostgreSQL is ready!"
    
    # Run migrations
    echo "Running database migrations..."
    alembic upgrade head || {
        echo "Migration failed, but continuing (database might already be up to date)"
    }
fi

# Execute the main command
exec "$@"