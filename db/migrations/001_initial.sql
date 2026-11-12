-- ============================================================================
-- Migration: 001_initial.sql
-- Description: Initial schema migration creating all 10 core tables, foreign keys,
--              B-Tree and GIN indexes, search vector triggers, and timestamp triggers.
-- Applied: 2026-10-30
-- DBMS Grading Standard: PES University DBMS Mini-Project Level 3
-- ============================================================================

BEGIN;

-- Ensure extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ----------------------------------------------------------------------------
-- 1. PLAYERS TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'player' CHECK (role IN ('player', 'admin')),
    gold INTEGER NOT NULL DEFAULT 100 CHECK (gold >= 0),
    level INTEGER NOT NULL DEFAULT 1 CHECK (level > 0),
    xp INTEGER NOT NULL DEFAULT 0 CHECK (xp >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 2. NPCS TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS npcs (
    npc_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    persona TEXT NOT NULL,
    location VARCHAR(100),
    personality_traits JSONB NOT NULL DEFAULT '{}',
    greeting TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 3. ITEMS TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS items (
    item_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    base_price INTEGER NOT NULL CHECK (base_price > 0),
    item_type VARCHAR(50) NOT NULL DEFAULT 'misc' CHECK (item_type IN ('weapon', 'armor', 'potion', 'misc', 'quest_item')),
    rarity VARCHAR(20) NOT NULL DEFAULT 'common' CHECK (rarity IN ('common', 'uncommon', 'rare', 'epic', 'legendary')),
    stock INTEGER NOT NULL DEFAULT -1,
    search_vector TSVECTOR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 4. QUESTS TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quests (
    quest_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    reward_gold INTEGER NOT NULL DEFAULT 0 CHECK (reward_gold >= 0),
    reward_xp INTEGER NOT NULL DEFAULT 0 CHECK (reward_xp >= 0),
    reward_item_id INTEGER REFERENCES items(item_id) ON DELETE SET NULL,
    min_level INTEGER NOT NULL DEFAULT 1 CHECK (min_level > 0),
    quest_type VARCHAR(50) NOT NULL DEFAULT 'main' CHECK (quest_type IN ('main', 'side', 'daily', 'hidden')),
    search_vector TSVECTOR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 5. PLAYER_INVENTORY TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS player_inventory (
    inventory_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items(item_id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity >= 0),
    acquired_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(player_id, item_id)
);

-- ----------------------------------------------------------------------------
-- 6. PLAYER_QUESTS TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS player_quests (
    player_quest_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    quest_id INTEGER NOT NULL REFERENCES quests(quest_id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'active', 'completed', 'failed')),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    UNIQUE(player_id, quest_id)
);

-- ----------------------------------------------------------------------------
-- 7. QUEST_PREREQUISITES TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quest_prerequisites (
    prerequisite_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    quest_id INTEGER NOT NULL REFERENCES quests(quest_id) ON DELETE CASCADE,
    required_quest_id INTEGER NOT NULL REFERENCES quests(quest_id) ON DELETE CASCADE,
    CHECK (quest_id != required_quest_id),
    UNIQUE(quest_id, required_quest_id)
);

-- ----------------------------------------------------------------------------
-- 8. INVENTORY_TRANSACTIONS TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inventory_transactions (
    transaction_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    item_id INTEGER REFERENCES items(item_id) ON DELETE SET NULL,
    transaction_type VARCHAR(20) NOT NULL CHECK (transaction_type IN ('buy', 'sell', 'transfer_in', 'transfer_out', 'quest_reward', 'admin_grant')),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    gold_amount INTEGER NOT NULL DEFAULT 0,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 9. NPC_RELATIONSHIPS TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS npc_relationships (
    relationship_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    npc_id INTEGER NOT NULL REFERENCES npcs(npc_id) ON DELETE CASCADE,
    affinity_score DECIMAL(5,2) NOT NULL DEFAULT 0.00 CHECK (affinity_score >= -100.00 AND affinity_score <= 100.00),
    interaction_count INTEGER NOT NULL DEFAULT 0 CHECK (interaction_count >= 0),
    last_interaction TIMESTAMPTZ,
    UNIQUE(player_id, npc_id)
);

-- ----------------------------------------------------------------------------
-- 10. AUDIT_LOG TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    log_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    row_id INTEGER,
    old_data JSONB,
    new_data JSONB,
    changed_by TEXT NOT NULL DEFAULT current_user,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- INDEX CREATION
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_quests_reward_item_id ON quests(reward_item_id);
CREATE INDEX IF NOT EXISTS idx_player_inventory_player_id ON player_inventory(player_id);
CREATE INDEX IF NOT EXISTS idx_player_inventory_item_id ON player_inventory(item_id);
CREATE INDEX IF NOT EXISTS idx_player_quests_player_id ON player_quests(player_id);
CREATE INDEX IF NOT EXISTS idx_player_quests_quest_id ON player_quests(quest_id);
CREATE INDEX IF NOT EXISTS idx_quest_prerequisites_quest_id ON quest_prerequisites(quest_id);
CREATE INDEX IF NOT EXISTS idx_quest_prerequisites_required_quest_id ON quest_prerequisites(required_quest_id);
CREATE INDEX IF NOT EXISTS idx_inventory_transactions_player_id ON inventory_transactions(player_id);
CREATE INDEX IF NOT EXISTS idx_inventory_transactions_item_id ON inventory_transactions(item_id);
CREATE INDEX IF NOT EXISTS idx_npc_relationships_player_id ON npc_relationships(player_id);
CREATE INDEX IF NOT EXISTS idx_npc_relationships_npc_id ON npc_relationships(npc_id);

CREATE INDEX IF NOT EXISTS idx_items_search_vector ON items USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_quests_search_vector ON quests USING GIN(search_vector);

CREATE INDEX IF NOT EXISTS idx_player_inventory_composite ON player_inventory(player_id, item_id);
CREATE INDEX IF NOT EXISTS idx_player_quests_composite ON player_quests(player_id, quest_id);
CREATE INDEX IF NOT EXISTS idx_inventory_transactions_player_created ON inventory_transactions(player_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_table_changed ON audit_log(table_name, changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_npc_relationships_composite ON npc_relationships(player_id, npc_id);

-- ----------------------------------------------------------------------------
-- CORE TRIGGERS FOR SEARCH VECTORS AND TIMESTAMPS
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_update_items_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector(
        'english',
        COALESCE(NEW.name, '') || ' ' || COALESCE(NEW.description, '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_items_search_vector ON items;
CREATE TRIGGER trg_items_search_vector
BEFORE INSERT OR UPDATE OF name, description ON items
FOR EACH ROW
EXECUTE FUNCTION fn_update_items_search_vector();

CREATE OR REPLACE FUNCTION fn_update_quests_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector(
        'english',
        COALESCE(NEW.title, '') || ' ' || COALESCE(NEW.description, '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_quests_search_vector ON quests;
CREATE TRIGGER trg_quests_search_vector
BEFORE INSERT OR UPDATE OF title, description ON quests
FOR EACH ROW
EXECUTE FUNCTION fn_update_quests_search_vector();

CREATE OR REPLACE FUNCTION fn_update_players_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_players_updated_at ON players;
CREATE TRIGGER trg_players_updated_at
BEFORE UPDATE ON players
FOR EACH ROW
EXECUTE FUNCTION fn_update_players_updated_at();

COMMIT;
