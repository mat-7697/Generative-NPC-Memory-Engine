-- ============================================================================
-- Generative NPC Memory Engine - Role-Based Access Control (RBAC) & RLS
-- Project: Generative NPC Memory Engine (PES University DBMS Mini-Project)
-- File: db/rbac.sql
-- Description: Security architecture defining database roles (app_admin, app_player),
--              table permissions, and Row-Level Security (RLS) policies enforcing
--              multi-tenant player data isolation and administrator overrides.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. ROLE PROVISIONING
-- Provision roles idempotently via anonymous PL/pgSQL DO block.
-- ----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin') THEN
        CREATE ROLE app_admin WITH NOLOGIN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_player') THEN
        CREATE ROLE app_player WITH NOLOGIN;
    END IF;
END;
$$;

-- ----------------------------------------------------------------------------
-- 2. HELPER FUNCTIONS FOR SESSION CONTEXT EXTRACTION
-- Extract current player identity and role from session variables safely.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION current_app_player_id()
RETURNS INT AS $$
BEGIN
    RETURN NULLIF(current_setting('app.current_player_id', true), '')::INT;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION is_app_admin()
RETURNS BOOLEAN AS $$
BEGIN
    RETURN (
        CURRENT_USER = 'app_admin'
        OR pg_has_role(CURRENT_USER, 'app_admin', 'MEMBER')
        OR current_setting('app.current_role', true) = 'admin'
    );
EXCEPTION WHEN OTHERS THEN
    RETURN FALSE;
END;
$$ LANGUAGE plpgsql STABLE;

-- ----------------------------------------------------------------------------
-- 3. PERMISSIONS GRANT & REVOKE
-- Configure least-privilege access for application roles.
-- ----------------------------------------------------------------------------

-- Schema usage
GRANT USAGE ON SCHEMA public TO app_admin, app_player;

-- Administrative Role Grants (Unrestricted access)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO app_admin;
GRANT ALL PRIVILEGES ON ALL ROUTINES IN SCHEMA public TO app_admin;

-- Player Role Grants (Constrained least-privilege)
-- Players table: Account lookup and self-profile updates
GRANT SELECT, INSERT, UPDATE ON players TO app_player;

-- Catalogs: Read-only access to NPCs, Items, Quests, Prerequisites
GRANT SELECT ON npcs, items, quests, quest_prerequisites TO app_player;

-- Inventory & Quests: CRUD restricted by RLS
GRANT SELECT, INSERT, UPDATE, DELETE ON player_inventory TO app_player;
GRANT SELECT, INSERT, UPDATE ON player_quests TO app_player;

-- Transactions Ledger: Append and view personal records
GRANT SELECT, INSERT ON inventory_transactions TO app_player;

-- NPC Relationships: View and update personal affinity records
GRANT SELECT, INSERT, UPDATE ON npc_relationships TO app_player;

-- Analytical Views: Read access
GRANT SELECT ON player_leaderboard, npc_popularity, quest_progress TO app_player;

-- Sequences & Stored Routines
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_player;
GRANT EXECUTE ON ALL ROUTINES IN SCHEMA public TO app_player;


-- ============================================================================
-- 4. ROW LEVEL SECURITY (RLS) CONFIGURATION
-- Enable RLS and define per-table policies for multi-tenant isolation.
-- ============================================================================

ALTER TABLE players ENABLE ROW LEVEL SECURITY;
ALTER TABLE player_inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE player_quests ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE npc_relationships ENABLE ROW LEVEL SECURITY;

-- ----------------------------------------------------------------------------
-- POLICIES: players TABLE
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS p_admin_all_players ON players;
CREATE POLICY p_admin_all_players ON players
    FOR ALL
    USING (is_app_admin())
    WITH CHECK (is_app_admin());

DROP POLICY IF EXISTS p_player_select_self ON players;
CREATE POLICY p_player_select_self ON players
    FOR SELECT
    USING (player_id = current_app_player_id());

DROP POLICY IF EXISTS p_player_update_self ON players;
CREATE POLICY p_player_update_self ON players
    FOR UPDATE
    USING (player_id = current_app_player_id())
    WITH CHECK (player_id = current_app_player_id());

DROP POLICY IF EXISTS p_player_insert_registration ON players;
CREATE POLICY p_player_insert_registration ON players
    FOR INSERT
    WITH CHECK (TRUE);


-- ----------------------------------------------------------------------------
-- POLICIES: player_inventory TABLE
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS p_admin_all_inventory ON player_inventory;
CREATE POLICY p_admin_all_inventory ON player_inventory
    FOR ALL
    USING (is_app_admin())
    WITH CHECK (is_app_admin());

DROP POLICY IF EXISTS p_player_inventory_isolation ON player_inventory;
CREATE POLICY p_player_inventory_isolation ON player_inventory
    FOR ALL
    USING (player_id = current_app_player_id())
    WITH CHECK (player_id = current_app_player_id());


-- ----------------------------------------------------------------------------
-- POLICIES: player_quests TABLE
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS p_admin_all_player_quests ON player_quests;
CREATE POLICY p_admin_all_player_quests ON player_quests
    FOR ALL
    USING (is_app_admin())
    WITH CHECK (is_app_admin());

DROP POLICY IF EXISTS p_player_quests_isolation ON player_quests;
CREATE POLICY p_player_quests_isolation ON player_quests
    FOR ALL
    USING (player_id = current_app_player_id())
    WITH CHECK (player_id = current_app_player_id());


-- ----------------------------------------------------------------------------
-- POLICIES: inventory_transactions TABLE
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS p_admin_all_transactions ON inventory_transactions;
CREATE POLICY p_admin_all_transactions ON inventory_transactions
    FOR ALL
    USING (is_app_admin())
    WITH CHECK (is_app_admin());

DROP POLICY IF EXISTS p_player_transactions_select ON inventory_transactions;
CREATE POLICY p_player_transactions_select ON inventory_transactions
    FOR SELECT
    USING (player_id = current_app_player_id());

DROP POLICY IF EXISTS p_player_transactions_insert ON inventory_transactions;
CREATE POLICY p_player_transactions_insert ON inventory_transactions
    FOR INSERT
    WITH CHECK (player_id = current_app_player_id());


-- ----------------------------------------------------------------------------
-- POLICIES: npc_relationships TABLE
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS p_admin_all_relationships ON npc_relationships;
CREATE POLICY p_admin_all_relationships ON npc_relationships
    FOR ALL
    USING (is_app_admin())
    WITH CHECK (is_app_admin());

DROP POLICY IF EXISTS p_player_relationships_isolation ON npc_relationships;
CREATE POLICY p_player_relationships_isolation ON npc_relationships
    FOR ALL
    USING (player_id = current_app_player_id())
    WITH CHECK (player_id = current_app_player_id());


-- ============================================================================
-- 5. APPLICATION INTEGRATION GUIDE: HOW TO SET SESSION VARIABLES
-- ============================================================================
/*
To utilize Row-Level Security in backend connection pools (e.g. FastAPI, SQLAlchemy,
or asyncpg), execute the following session commands upon acquiring a connection:

1. Setting the active player context:
   SET LOCAL app.current_player_id = '42';
   SET LOCAL app.current_role = 'player';

2. Setting administrative context (Bypass RLS):
   SET LOCAL app.current_player_id = '1';
   SET LOCAL app.current_role = 'admin';

In Python (asyncpg / FastAPI dependency):
```python
async with db_pool.acquire() as connection:
    async with connection.transaction():
        await connection.execute(
            "SET LOCAL app.current_player_id = $1;", str(user.player_id)
        )
        await connection.execute(
            "SET LOCAL app.current_role = $1;", user.role
        )
        # All queries in this block will now automatically be filtered by RLS!
        inventory = await connection.fetch("SELECT * FROM player_inventory;")
```
*/
