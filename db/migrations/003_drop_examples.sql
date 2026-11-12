-- ============================================================================
-- Migration: 003_drop_examples.sql
-- Description: Demonstrates Data Definition Language (DDL) teardown and cleanup
--              operations using DROP statements for database objects.
-- Rubric Criteria: DDL Object Destruction, Idempotent Drops, Cascade Effects
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. DROP INDEX IF EXISTS
-- Safely removes a secondary index without impacting underlying table data.
-- ----------------------------------------------------------------------------
-- Create demo index first to ensure safe, reproducible demonstration
CREATE INDEX IF NOT EXISTS idx_demo_temp_players_email ON players(email);

-- Drop the index idempotently
DROP INDEX IF EXISTS idx_demo_temp_players_email;


-- ----------------------------------------------------------------------------
-- 2. DROP TRIGGER IF EXISTS
-- Removes an active event trigger bound to a database table.
-- ----------------------------------------------------------------------------
-- Create demo trigger function and trigger to demonstrate teardown
CREATE OR REPLACE FUNCTION fn_demo_temp_logger()
RETURNS TRIGGER AS $$
BEGIN
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_demo_temp_audit
AFTER UPDATE ON players
FOR EACH ROW
EXECUTE FUNCTION fn_demo_temp_logger();

-- Idempotently drop the trigger
DROP TRIGGER IF EXISTS trg_demo_temp_audit ON players;


-- ----------------------------------------------------------------------------
-- 3. DROP FUNCTION IF EXISTS
-- Removes a stored PL/pgSQL function from the schema catalog.
-- ----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS fn_demo_temp_logger();


-- ----------------------------------------------------------------------------
-- 4. ALTER TABLE DROP COLUMN IF EXISTS
-- Alters table structure by removing an obsolete column and its dependencies.
-- ----------------------------------------------------------------------------
-- Create demo column
ALTER TABLE players ADD COLUMN IF NOT EXISTS temp_session_token TEXT;

-- Drop the column
ALTER TABLE players DROP COLUMN IF EXISTS temp_session_token;


-- ----------------------------------------------------------------------------
-- 5. DROP TABLE IF EXISTS (DEMO TABLE WITH CASCADE)
-- Illustrates dropping an entire table including dependent constraints and sequences.
-- ----------------------------------------------------------------------------
-- Create temporary staging table
CREATE TABLE IF NOT EXISTS demo_quest_archive (
    archive_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    archived_quest_id INTEGER,
    archived_title VARCHAR(200),
    archived_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Safely and cleanly drop the demo table
DROP TABLE IF EXISTS demo_quest_archive CASCADE;

COMMIT;
