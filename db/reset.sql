-- ============================================================================
-- Generative NPC Memory Engine - Database Teardown & Reset Script
-- Project: Generative NPC Memory Engine (DBMS Mini-Project - PES University)
-- File: db/reset.sql
-- Description: EXPLICIT destructive teardown script for development reset.
--              WARNING: Executing this script permanently drops all application
--              tables, views, types, and data.
-- ============================================================================

BEGIN;

-- Drop dependent views
DROP VIEW IF EXISTS quest_progress CASCADE;
DROP VIEW IF EXISTS npc_popularity CASCADE;
DROP VIEW IF EXISTS player_leaderboard CASCADE;

-- Drop application tables in reverse dependency order
DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS npc_relationships CASCADE;
DROP TABLE IF EXISTS inventory_transactions CASCADE;
DROP TABLE IF EXISTS quest_prerequisites CASCADE;
DROP TABLE IF EXISTS player_quests CASCADE;
DROP TABLE IF EXISTS player_inventory CASCADE;
DROP TABLE IF EXISTS quests CASCADE;
DROP TABLE IF EXISTS items CASCADE;
DROP TABLE IF EXISTS npcs CASCADE;
DROP TABLE IF EXISTS players CASCADE;

COMMIT;
