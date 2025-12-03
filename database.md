# Database Setup

This guide outlines the PostgreSQL role, schema, and table structure needed for
the tv API. The design keeps ownership scoped to a dedicated application role
while modeling users, artworks, purchasable videos, and fine-grained download
entitlements.

## 1. Create Roles and Schema

Run the following statements as a superuser (e.g., `psql -U postgres`):

```sql
CREATE ROLE tv_api_app WITH LOGIN PASSWORD 'changeme' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE SCHEMA tv_app AUTHORIZATION tv_api_app;
GRANT USAGE ON SCHEMA tv_app TO tv_api_app;
ALTER ROLE tv_api_app IN DATABASE tv_dbase SET search_path = tv_app, public;

-- Optional read-only role
CREATE ROLE tv_api_readonly NOLOGIN;
GRANT USAGE ON SCHEMA tv_app TO tv_api_readonly;
```

Grant table/sequence rights (and set defaults so future tables inherit them):

```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA tv_app TO tv_api_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA tv_app TO tv_api_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA tv_app
	GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO tv_api_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA tv_app
	GRANT USAGE, SELECT ON SEQUENCES TO tv_api_app;
```

## 2. Core Tables

```sql
CREATE TABLE tv_app.users (
	user_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	email          CITEXT NOT NULL UNIQUE,
	display_name   TEXT,
	created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE tv_app.art_pieces (
	art_piece_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	slug           TEXT NOT NULL UNIQUE,
	title          TEXT NOT NULL,
	artist_name    TEXT,
	description    TEXT,
	created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE tv_app.art_videos (
	art_video_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	art_piece_id   UUID NOT NULL REFERENCES tv_app.art_pieces(art_piece_id) ON DELETE CASCADE,
	variant_label  TEXT NOT NULL,
	file_uri       TEXT NOT NULL,
	checksum       TEXT,
	duration_secs  INTEGER,
	is_downloadable BOOLEAN NOT NULL DEFAULT TRUE,
	created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	UNIQUE (art_piece_id, variant_label)
);

CREATE TABLE tv_app.user_art_purchases (
	purchase_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	user_id        UUID NOT NULL REFERENCES tv_app.users(user_id) ON DELETE CASCADE,
	art_piece_id   UUID NOT NULL REFERENCES tv_app.art_pieces(art_piece_id) ON DELETE CASCADE,
	purchase_ref   TEXT NOT NULL,
	purchased_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	UNIQUE (user_id, art_piece_id)
);

CREATE TABLE tv_app.user_video_entitlements (
	entitlement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	user_id        UUID NOT NULL REFERENCES tv_app.users(user_id) ON DELETE CASCADE,
	art_video_id   UUID NOT NULL REFERENCES tv_app.art_videos(art_video_id) ON DELETE CASCADE,
	granted_via    UUID REFERENCES tv_app.user_art_purchases(purchase_id),
	granted_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	UNIQUE (user_id, art_video_id)
);
```

## 3. Helpful Indexes

```sql
CREATE INDEX idx_users_email_lower ON tv_app.users (LOWER(email));
CREATE INDEX idx_purchases_user ON tv_app.user_art_purchases (user_id);
CREATE INDEX idx_entitlements_user ON tv_app.user_video_entitlements (user_id);
```

Add additional indexes (e.g., on `slug`, `art_piece_id`) as query patterns evolve.

## 4. Usage Examples

**List user downloads**

```sql
SELECT v.art_video_id, v.variant_label, v.file_uri
FROM tv_app.art_videos v
JOIN tv_app.user_video_entitlements e ON e.art_video_id = v.art_video_id
JOIN tv_app.users u ON u.user_id = e.user_id
WHERE u.email = 'collector@example.com'
  AND v.is_downloadable;
```

**Insert purchase + entitlements** (pseudo-transaction):

```sql
BEGIN;

WITH new_purchase AS (
	INSERT INTO tv_app.user_art_purchases (user_id, art_piece_id, purchase_ref)
	VALUES (:user_id, :art_piece_id, :order_id)
	RETURNING purchase_id
)
INSERT INTO tv_app.user_video_entitlements (user_id, art_video_id, granted_via)
SELECT :user_id, v.art_video_id, new_purchase.purchase_id
FROM tv_app.art_videos v
CROSS JOIN new_purchase
WHERE v.art_piece_id = :art_piece_id
  AND should_unlock_variant(v.variant_label); -- application decides

COMMIT;
```

This document should keep database creation reproducible while clarifying how
user purchases unlock specific video assets.

## 5. Automated Recreate Script

Use the helper script to drop and recreate the database, role, schema, and tables
in one go. The first argument is the password to assign to `tv_api_app` (or the
user specified via `TV_APP_USER`).



```bash
export PGPASSWORD='superuser-secret'
./scripts/recreate_database.sh 'changeme'
```

Environment overrides:

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `PGHOST` | `localhost` | PostgreSQL host to connect to |
| `PGPORT` | `5432` | PostgreSQL port |
| `PG_SUPERUSER` | `postgres` | Superuser used to run DDL |
| `TV_DB_NAME` | `tv_dbase` | Database name to recreate |
| `TV_APP_USER` | `tv_api_app` | Application role name |
| `TV_APP_SCHEMA` | `tv_app` | Schema for tables |

The script uses `db/schema.sql` for the table definitions and prints a reminder
to run the seed file when it completes.

## 6. Seed Script

Use `db/seed.sql` to load baseline data for local development:

```bash
psql "postgresql://tv_api_app:change_me@localhost:5432/your_db" -f db/seed.sql
```

The script is idempotent via `ON CONFLICT` clauses, so it can be re-run safely.
