-- ============================================================================
-- Generative NPC Memory Engine - Master Database Initializer
-- Execution Order:
--   1. Schema (Tables, Constraints, Base FTS Triggers)
--   2. Stored Procedures & Functions (ACID procedures, can_start_quest function)
--   3. Relational Views (player_leaderboard, npc_popularity, quest_progress)
--   4. Triggers (Auditing, Invariant checks, Auto level-up)
--   5. Seed Data (Idempotent seed data with sequence realignment)
--   6. RBAC & Row-Level Security (Roles, Grants, RLS policies)
-- ============================================================================

\i /db-scripts/schema.sql
\i /db-scripts/procedures.sql
\i /db-scripts/views.sql
\i /db-scripts/triggers.sql
\i /db-scripts/seed.sql
\i /db-scripts/rbac.sql
