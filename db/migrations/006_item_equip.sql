-- ============================================================================
-- Migration 006: Add is_equipped flag to player_inventory for active gear slots
-- ============================================================================

ALTER TABLE player_inventory 
ADD COLUMN IF NOT EXISTS is_equipped BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN player_inventory.is_equipped IS 'Tracks whether a weapon, armor piece, or amulet is actively equipped by the player';
