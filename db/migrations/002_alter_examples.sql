-- ============================================================================
-- Migration: 002_alter_examples.sql
-- Description: Demonstrates Data Definition Language (DDL) Schema Evolution using
--              ALTER TABLE and CREATE INDEX operations.
-- Rubric Criteria: DDL Alterations, Constraint Enforcement, Index Creation, Schema Evolution
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. ADD COLUMN TO EXISTING TABLE
-- Requirement: Add 'last_login' timestamp column to players table to track
-- active user sessions and inactivity durations.
-- ----------------------------------------------------------------------------
ALTER TABLE players 
ADD COLUMN IF NOT EXISTS last_login TIMESTAMPTZ;

COMMENT ON COLUMN players.last_login IS 'Timestamp recording the most recent player login event';

-- ----------------------------------------------------------------------------
-- 2. ALTER COLUMN PROPERTIES (DEFAULT & NOT NULL)
-- Requirement: Change items.description from NULLable to NOT NULL with default ''.
-- First ensure default is set, backfill existing NULLs to avoid constraint violation,
-- and then apply the NOT NULL constraint.
-- ----------------------------------------------------------------------------
-- Step A: Set new default value
ALTER TABLE items 
ALTER COLUMN description SET DEFAULT '';

-- Step B: Backfill existing NULL entries to empty string
UPDATE items 
SET description = '' 
WHERE description IS NULL;

-- Step C: Enforce NOT NULL constraint
ALTER TABLE items 
ALTER COLUMN description SET NOT NULL;

-- ----------------------------------------------------------------------------
-- 3. ADD TABLE-LEVEL CHECK CONSTRAINT
-- Requirement: Enforce that for all purchase transactions ('buy'), the gold_amount
-- deducted must be non-negative (>= 0).
-- ----------------------------------------------------------------------------
ALTER TABLE inventory_transactions 
ADD CONSTRAINT chk_inventory_tx_buy_gold 
CHECK (transaction_type != 'buy' OR gold_amount >= 0);

COMMENT ON CONSTRAINT chk_inventory_tx_buy_gold ON inventory_transactions 
IS 'Ensures that purchases require a non-negative gold expenditure';

-- ----------------------------------------------------------------------------
-- 4. CREATE SECONDARY INDEX FOR QUERY ACCELERATION
-- Requirement: Accelerate query filtering and sorting by player session activity.
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_players_last_login 
ON players(last_login DESC NULLS LAST);

COMMIT;
