-- Core schema for PickleTV API database
SET client_min_messages TO WARNING;

CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

\if :{?schema_name}
\else
\set schema_name tv_app
\endif

SET search_path = :'schema_name', public;

CREATE TABLE users (
    user_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email          CITEXT NOT NULL UNIQUE,
    display_name   TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE art_pieces (
    art_piece_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug           TEXT NOT NULL UNIQUE,
    title          TEXT NOT NULL,
    artist_name    TEXT,
    description    TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE art_videos (
    art_video_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    art_piece_id    UUID NOT NULL REFERENCES art_pieces(art_piece_id) ON DELETE CASCADE,
    variant_label   TEXT NOT NULL,
    file_uri        TEXT NOT NULL,
    checksum        TEXT,
    duration_secs   INTEGER,
    is_downloadable BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (art_piece_id, variant_label)
);

CREATE TABLE user_art_purchases (
    purchase_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    art_piece_id  UUID NOT NULL REFERENCES art_pieces(art_piece_id) ON DELETE CASCADE,
    purchase_ref  TEXT NOT NULL,
    purchased_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, art_piece_id)
);

CREATE TABLE user_video_entitlements (
    entitlement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    art_video_id   UUID NOT NULL REFERENCES art_videos(art_video_id) ON DELETE CASCADE,
    granted_via    UUID REFERENCES user_art_purchases(purchase_id),
    granted_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, art_video_id)
);

CREATE INDEX idx_users_email_lower ON users (LOWER(email));
CREATE INDEX idx_purchases_user ON user_art_purchases (user_id);
CREATE INDEX idx_entitlements_user ON user_video_entitlements (user_id);

-- Magic Link Authentication
CREATE TABLE magic_links (
    magic_link_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token               TEXT NOT NULL UNIQUE,
    email               CITEXT NOT NULL,
    device_id           TEXT NOT NULL,
    device_model        TEXT,
    device_manufacturer TEXT,
    platform            TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMPTZ NOT NULL,
    used                BOOLEAN DEFAULT FALSE,
    used_at             TIMESTAMPTZ
);

CREATE INDEX idx_magic_links_token ON magic_links(token);
CREATE INDEX idx_magic_links_email ON magic_links(email);
CREATE INDEX idx_magic_links_device_id ON magic_links(device_id);
CREATE INDEX idx_magic_links_expires_at ON magic_links(expires_at) WHERE NOT used;

-- User Content
CREATE TABLE user_content (
    content_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    description     TEXT,
    video_filename  TEXT NOT NULL,
    thumbnail_filename TEXT,
    duration_secs   INTEGER,
    file_size_bytes BIGINT,
    is_public       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_user_content_user_id ON user_content(user_id);
CREATE INDEX idx_user_content_public ON user_content(is_public) WHERE is_public = TRUE;
