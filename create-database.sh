#!/bin/bash

if ! command -v psql >/dev/null 2>&1; then
    echo "Error: psql is not installed."
    echo "On Amazon Linux, install it with: sudo yum install postgresql15"
    exit 1
fi

PGHOST="comp5349-tyin4383-a1-db.chi8eme8yqe0.ap-southeast-2.rds.amazonaws.com"
PGPORT="5432"
PGDATABASE="postgres"
PGUSER="postgres"
PGPASSWORD="aFX9mCMh3GDq3LpIgtwD"

export PGPASSWORD

psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" <<EOF
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    s3_key TEXT NOT NULL,
    summary TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'completed',
    uploaded_at TIMESTAMP NOT NULL
);
EOF

echo "Table 'documents' created successfully."
