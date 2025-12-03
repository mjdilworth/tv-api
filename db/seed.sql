\echo '>> Seeding baseline PickleTV data'
\set ON_ERROR_STOP on

BEGIN;

WITH upsert_users AS (
    INSERT INTO tv_app.users (email, display_name)
    VALUES
        ('collector@example.com', 'Collector One'),
        ('vip@example.com', 'VIP Patron')
    ON CONFLICT (email) DO UPDATE
        SET display_name = EXCLUDED.display_name
    RETURNING user_id, email
),
upsert_art_pieces AS (
    INSERT INTO tv_app.art_pieces (slug, title, artist_name, description)
    VALUES
        ('cosmic-dreams', 'Cosmic Dreams', 'Aria Vega', 'Immersive cosmic landscape'),
        ('neon-echoes', 'Neon Echoes', 'Milo Hart', 'Synthwave-inspired loop')
    ON CONFLICT (slug) DO UPDATE
        SET title = EXCLUDED.title,
            artist_name = EXCLUDED.artist_name,
            description = EXCLUDED.description
    RETURNING art_piece_id, slug
),
upsert_videos AS (
    INSERT INTO tv_app.art_videos (
        art_piece_id,
        variant_label,
        file_uri,
        checksum,
        duration_secs,
        is_downloadable
    )
    SELECT ap.art_piece_id, data.variant_label, data.file_uri, data.checksum, data.duration_secs, data.is_downloadable
    FROM upsert_art_pieces ap
    JOIN (
        VALUES
            ('cosmic-dreams', '4k-loop', '/mnt/media/cosmic_dreams/4k_loop.mp4', 'sha256:abc123', 180, true),
            ('cosmic-dreams', 'making-of', 'https://cdn.pickletv.example/cosmic/making_of.mp4', NULL, 360, false),
            ('neon-echoes', '8k-master', '/mnt/media/neon_echoes/8k_master.mp4', 'sha256:def456', 240, true)
    ) AS data(slug, variant_label, file_uri, checksum, duration_secs, is_downloadable)
        ON data.slug = ap.slug
    ON CONFLICT (art_piece_id, variant_label) DO UPDATE
        SET file_uri = EXCLUDED.file_uri,
            checksum = EXCLUDED.checksum,
            duration_secs = EXCLUDED.duration_secs,
            is_downloadable = EXCLUDED.is_downloadable
    RETURNING art_video_id, art_piece_id, variant_label
),
collector AS (
    SELECT user_id FROM upsert_users WHERE email = 'collector@example.com'
),
cosmic AS (
    SELECT art_piece_id FROM upsert_art_pieces WHERE slug = 'cosmic-dreams'
),
neon AS (
    SELECT art_piece_id FROM upsert_art_pieces WHERE slug = 'neon-echoes'
),
inserting_purchases AS (
    INSERT INTO tv_app.user_art_purchases (user_id, art_piece_id, purchase_ref)
    SELECT collector.user_id, cosmic.art_piece_id, 'ORDER-1001'
    FROM collector, cosmic
    UNION ALL
    SELECT collector.user_id, neon.art_piece_id, 'ORDER-1002'
    FROM collector, neon
    ON CONFLICT (user_id, art_piece_id) DO UPDATE
        SET purchase_ref = EXCLUDED.purchase_ref
    RETURNING purchase_id, user_id, art_piece_id
)
INSERT INTO tv_app.user_video_entitlements (user_id, art_video_id, granted_via)
SELECT purchases.user_id, vids.art_video_id, purchases.purchase_id
FROM inserting_purchases purchases
JOIN upsert_videos vids ON vids.art_piece_id = purchases.art_piece_id
WHERE vids.variant_label <> 'making-of'
ON CONFLICT (user_id, art_video_id) DO NOTHING;

COMMIT;

\echo '>> Seed complete'
