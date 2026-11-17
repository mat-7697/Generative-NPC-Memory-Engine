"""One-step local database setup (no Docker, no psql needed).

Creates the `npc_memory_engine` database on your local PostgreSQL and loads
schema, procedures, views, triggers, seed data and RBAC in the right order.

Usage (from the backend folder, with the venv active):
    python setup_db.py           # create database if missing and load everything
    python setup_db.py --reset   # drop and recreate the database from scratch
"""

import asyncio
import sys
from pathlib import Path

import asyncpg

from app.config import get_settings

DB_DIR = Path(__file__).resolve().parent.parent / "db"
SCRIPTS = ["schema.sql", "procedures.sql", "views.sql", "triggers.sql", "seed.sql", "rbac.sql"]

# Idempotent upgrades applied on every run so existing databases pick up
# columns/constraints the application code depends on.
UPGRADES = """
ALTER TABLE player_inventory ADD COLUMN IF NOT EXISTS is_equipped BOOLEAN NOT NULL DEFAULT FALSE;

DO $$
DECLARE c TEXT;
BEGIN
    FOR c IN
        SELECT conname FROM pg_constraint
        WHERE conrelid = 'inventory_transactions'::regclass AND contype = 'c'
          AND pg_get_constraintdef(oid) LIKE '%transaction_type%'
    LOOP
        EXECUTE format('ALTER TABLE inventory_transactions DROP CONSTRAINT %I', c);
    END LOOP;
END $$;

ALTER TABLE inventory_transactions ADD CONSTRAINT inventory_transactions_transaction_type_check
    CHECK (transaction_type IN ('buy', 'sell', 'transfer_in', 'transfer_out', 'quest_reward', 'admin_grant',
                                'consume_item', 'battle_loot', 'inn_rest'));
"""


async def main(reset: bool) -> None:
    s = get_settings()
    conn_args = dict(host=s.pg_host, port=s.pg_port, user=s.pg_user, password=s.pg_password)

    try:
        admin = await asyncpg.connect(database="postgres", **conn_args)
    except Exception as exc:
        print(f"\n[X] Could not connect to PostgreSQL at {s.pg_host}:{s.pg_port} as '{s.pg_user}'.")
        print(f"    Reason: {exc}")
        print("    -> Make sure PostgreSQL is running, and set PG_PASSWORD (and the password inside")
        print("       DATABASE_URL) in backend\\.env to your real postgres password.")
        sys.exit(1)

    exists = await admin.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", s.pg_database)
    if exists and reset:
        print(f"Dropping database '{s.pg_database}'...")
        await admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = $1 AND pid <> pg_backend_pid()",
            s.pg_database,
        )
        await admin.execute(f'DROP DATABASE "{s.pg_database}"')
        exists = False
    if not exists:
        print(f"Creating database '{s.pg_database}'...")
        await admin.execute(f'CREATE DATABASE "{s.pg_database}"')
    await admin.close()

    conn = await asyncpg.connect(database=s.pg_database, **conn_args)
    already = await conn.fetchval("SELECT to_regclass('public.players') IS NOT NULL")
    if already and not reset:
        print("Tables already exist - skipping load (use --reset to rebuild from scratch).")
    else:
        for name in SCRIPTS:
            print(f"Loading {name}...")
            await conn.execute((DB_DIR / name).read_text(encoding="utf-8"))
        print("Loading quest challenges...")
        await conn.execute((DB_DIR / "migrations" / "007_quest_challenge_refresh.sql").read_text(encoding="utf-8"))

    print("Applying schema upgrades...")
    await conn.execute(UPGRADES)

    if not await conn.fetchval("SELECT to_regclass('public.monsters') IS NOT NULL"):
        print("Installing combat campaign (monsters, battles, item stats)...")
        await conn.execute((DB_DIR / "migrations" / "008_combat_campaign.sql").read_text(encoding="utf-8"))

    players = await conn.fetch("SELECT username, role FROM players ORDER BY player_id")
    await conn.close()
    print("\n[OK] Database ready. Accounts:", ", ".join(f"{p['username']} ({p['role']})" for p in players))


if __name__ == "__main__":
    asyncio.run(main(reset="--reset" in sys.argv))
