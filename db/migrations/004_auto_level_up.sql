-- Function to calculate RPG level from total XP
CREATE OR REPLACE FUNCTION fn_calculate_level(p_xp INTEGER)
RETURNS INTEGER AS $$
BEGIN
    RETURN CASE 
        WHEN p_xp >= 50000 THEN 20
        WHEN p_xp >= 15000 THEN 10
        WHEN p_xp >= 8000 THEN 8
        WHEN p_xp >= 4000 THEN 6
        WHEN p_xp >= 2000 THEN 5
        WHEN p_xp >= 1000 THEN 4
        WHEN p_xp >= 300 THEN 3
        WHEN p_xp >= 100 THEN 2
        ELSE 1
    END;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Trigger to auto-advance player level on XP increase
CREATE OR REPLACE FUNCTION fn_auto_level_up()
RETURNS TRIGGER AS $$
BEGIN
    NEW.level := GREATEST(NEW.level, fn_calculate_level(NEW.xp));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_auto_level_up ON players;
CREATE TRIGGER trg_auto_level_up
BEFORE INSERT OR UPDATE OF xp ON players
FOR EACH ROW
EXECUTE FUNCTION fn_auto_level_up();

-- Recalculate level for all existing accounts
UPDATE players SET level = fn_calculate_level(xp);

-- Display updated stats
SELECT player_id, username, level, xp, gold FROM players ORDER BY player_id;
