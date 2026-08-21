"""PostgreSQL connection and schema helpers for the item catalogue."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row


DEFAULT_DATABASE_URL = "postgresql://true_roi:true_roi@localhost:5432/true_roi"


def database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


@contextmanager
def get_connection() -> Iterator[Connection]:
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        yield connection


def ensure_schema(connection: Connection) -> None:
    """Create the small catalogue schema. Safe to call on every import."""
    connection.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS skins (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            image_url TEXT,
            weapon_id TEXT,
            weapon_name TEXT,
            category_id TEXT,
            category_name TEXT,
            pattern_id TEXT,
            pattern_name TEXT,
            rarity_id TEXT,
            rarity_name TEXT,
            rarity_color TEXT,
            min_float DOUBLE PRECISION,
            max_float DOUBLE PRECISION,
            paint_index TEXT,
            has_stattrak BOOLEAN NOT NULL DEFAULT FALSE,
            has_souvenir BOOLEAN NOT NULL DEFAULT FALSE,
            raw_data JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS skin_variants (
            id TEXT PRIMARY KEY,
            skin_id TEXT NOT NULL REFERENCES skins(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            market_hash_name TEXT,
            wear_id TEXT,
            wear_name TEXT,
            stattrak BOOLEAN NOT NULL DEFAULT FALSE,
            souvenir BOOLEAN NOT NULL DEFAULT FALSE,
            image_url TEXT,
            raw_data JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS skins_name_trgm_idx "
        "ON skins USING GIN (LOWER(name) gin_trgm_ops)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS skins_weapon_idx ON skins (weapon_name)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS skins_rarity_idx ON skins (rarity_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS skin_variants_skin_idx ON skin_variants (skin_id)"
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS skin_collections (
            skin_id TEXT NOT NULL REFERENCES skins(id) ON DELETE CASCADE,
            collection_id TEXT NOT NULL,
            collection_name TEXT NOT NULL,
            image_url TEXT,
            PRIMARY KEY (skin_id, collection_id)
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS skin_collections_collection_idx "
        "ON skin_collections (collection_id, skin_id)"
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS marketplace_listings (
            marketplace TEXT NOT NULL,
            variant_id TEXT NOT NULL REFERENCES skin_variants(id) ON DELETE CASCADE,
            listing_id TEXT,
            price_cents INTEGER CHECK (price_cents >= 0),
            item_url TEXT,
            float_value DOUBLE PRECISION,
            quantity INTEGER CHECK (quantity >= 0),
            is_available BOOLEAN NOT NULL DEFAULT FALSE,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (marketplace, variant_id)
        )
        """
    )
    connection.execute(
        "ALTER TABLE marketplace_listings "
        "ADD COLUMN IF NOT EXISTS quantity INTEGER CHECK (quantity >= 0)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS marketplace_listings_fetched_idx "
        "ON marketplace_listings (marketplace, fetched_at)"
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS marketplace_syncs (
            marketplace TEXT PRIMARY KEY,
            fetched_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS marketplace_variant_details (
            marketplace TEXT NOT NULL,
            variant_id TEXT NOT NULL REFERENCES skin_variants(id) ON DELETE CASCADE,
            sales_count INTEGER CHECK (sales_count >= 0),
            liquidity_score INTEGER CHECK (liquidity_score BETWEEN 0 AND 100),
            liquidity_label TEXT,
            listings JSONB NOT NULL DEFAULT '[]'::JSONB,
            sales JSONB NOT NULL DEFAULT '[]'::JSONB,
            buy_orders JSONB NOT NULL DEFAULT '[]'::JSONB,
            listings_error TEXT,
            sales_error TEXT,
            buy_orders_error TEXT,
            details_version SMALLINT NOT NULL DEFAULT 1,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (marketplace, variant_id)
        )
        """
    )
    connection.execute(
        "ALTER TABLE marketplace_variant_details "
        "ADD COLUMN IF NOT EXISTS sales JSONB NOT NULL DEFAULT '[]'::JSONB"
    )
    connection.execute(
        "ALTER TABLE marketplace_variant_details "
        "ADD COLUMN IF NOT EXISTS buy_orders JSONB NOT NULL DEFAULT '[]'::JSONB"
    )
    connection.execute(
        "ALTER TABLE marketplace_variant_details "
        "ADD COLUMN IF NOT EXISTS buy_orders_error TEXT"
    )
    connection.execute(
        "ALTER TABLE marketplace_variant_details "
        "ADD COLUMN IF NOT EXISTS details_version SMALLINT NOT NULL DEFAULT 1"
    )
