-- ============================================================================
-- Generative NPC Memory Engine - Database Triggers
-- Project: Generative NPC Memory Engine (PES University DBMS Mini-Project)
-- File: db/triggers.sql
-- Description: Advanced event triggers for audit logging, business invariant
--              enforcement, automated quest reward fulfillment, and timestamp
--              maintenance.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- TRIGGER A: Audit Trigger on player_inventory
-- Event: AFTER INSERT OR UPDATE OR DELETE
-- Action: Captures all inventory mutations in audit_log as JSONB snapshots.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_audit_player_inventory()
RETURNS TRIGGER AS $$
DECLARE
    v_row_id INTEGER;
    v_old JSONB := NULL;
    v_new JSONB := NULL;
BEGIN
    IF TG_OP = 'INSERT' THEN
        v_row_id := NEW.inventory_id;
        v_new := to_jsonb(NEW);
    ELSIF TG_OP = 'UPDATE' THEN
        v_row_id := NEW.inventory_id;
        v_old := to_jsonb(OLD);
        v_new := to_jsonb(NEW);
    ELSIF TG_OP = 'DELETE' THEN
        v_row_id := OLD.inventory_id;
        v_old := to_jsonb(OLD);
    END IF;

    INSERT INTO audit_log (
        table_name,
        operation,
        row_id,
        old_data,
        new_data,
        changed_by,
        changed_at
    ) VALUES (
        'player_inventory',
        TG_OP,
        v_row_id,
        v_old,
        v_new,
        CURRENT_USER,
        NOW()
    );

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_player_inventory ON player_inventory;
CREATE TRIGGER trg_audit_player_inventory
AFTER INSERT OR UPDATE OR DELETE ON player_inventory
FOR EACH ROW
EXECUTE FUNCTION fn_audit_player_inventory();


-- ----------------------------------------------------------------------------
-- TRIGGER B: Audit Trigger on players (Gold Changes)
-- Event: AFTER UPDATE OF gold ON players
-- Action: Logs changes in player treasury balances with old vs new amounts.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_audit_players_gold()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO audit_log (
        table_name,
        operation,
        row_id,
        old_data,
        new_data,
        changed_by,
        changed_at
    ) VALUES (
        'players',
        'UPDATE',
        NEW.player_id,
        jsonb_build_object('player_id', OLD.player_id, 'username', OLD.username, 'gold', OLD.gold),
        jsonb_build_object('player_id', NEW.player_id, 'username', NEW.username, 'gold', NEW.gold),
        CURRENT_USER,
        NOW()
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_players_gold ON players;
CREATE TRIGGER trg_audit_players_gold
AFTER UPDATE OF gold ON players
FOR EACH ROW
WHEN (OLD.gold IS DISTINCT FROM NEW.gold)
EXECUTE FUNCTION fn_audit_players_gold();


-- ----------------------------------------------------------------------------
-- TRIGGER C: Block Negative Gold Invariant
-- Event: BEFORE UPDATE ON players
-- Action: Aborts transaction if gold would drop below zero.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_block_negative_gold()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.gold < 0 THEN
        RAISE EXCEPTION 'Insufficient gold: Balance cannot be negative. Attempted value: %', NEW.gold;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_block_negative_gold ON players;
CREATE TRIGGER trg_block_negative_gold
BEFORE UPDATE ON players
FOR EACH ROW
EXECUTE FUNCTION fn_block_negative_gold();


-- ----------------------------------------------------------------------------
-- TRIGGER D: Block Negative Inventory Quantity Invariant
-- Event: BEFORE UPDATE ON player_inventory
-- Action: Prevents inventory items from dropping below 0 quantity.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_block_negative_quantity()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.quantity < 0 THEN
        RAISE EXCEPTION 'Insufficient quantity: Inventory count cannot be negative. Attempted quantity: %', NEW.quantity;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_block_negative_quantity ON player_inventory;
CREATE TRIGGER trg_block_negative_quantity
BEFORE UPDATE ON player_inventory
FOR EACH ROW
EXECUTE FUNCTION fn_block_negative_quantity();


-- ----------------------------------------------------------------------------
-- TRIGGER E: Quest Completion Automated Reward Fulfillment
-- Event: AFTER UPDATE OF status ON player_quests
-- Condition: status transitions to 'completed'
-- Action: Automatically credits player gold, grants XP, provisions reward
--         items into player_inventory, and registers an inventory_transactions entry.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_reward_quest_completion()
RETURNS TRIGGER AS $$
DECLARE
    v_quest RECORD;
BEGIN
    -- Retrieve quest reward specifications
    SELECT reward_gold, reward_xp, reward_item_id, title
    INTO v_quest
    FROM quests
    WHERE quest_id = NEW.quest_id;

    IF NOT FOUND THEN
        RETURN NEW;
    END IF;

    -- 1. Disburse gold and XP progression rewards to the player
    UPDATE players
    SET gold = gold + v_quest.reward_gold,
        xp = xp + v_quest.reward_xp,
        updated_at = NOW()
    WHERE player_id = NEW.player_id;

    -- 2. Disburse item reward if configured for this quest
    IF v_quest.reward_item_id IS NOT NULL THEN
        -- Upsert item in player inventory
        INSERT INTO player_inventory (player_id, item_id, quantity, acquired_at)
        VALUES (NEW.player_id, v_quest.reward_item_id, 1, NOW())
        ON CONFLICT (player_id, item_id)
        DO UPDATE SET quantity = player_inventory.quantity + 1;

        -- Record transaction entry in the immutable ledger
        INSERT INTO inventory_transactions (
            player_id,
            item_id,
            transaction_type,
            quantity,
            gold_amount,
            description,
            created_at
        ) VALUES (
            NEW.player_id,
            v_quest.reward_item_id,
            'quest_reward',
            1,
            v_quest.reward_gold,
            'Reward for completing Quest #' || NEW.quest_id || ': ' || v_quest.title,
            NOW()
        );
    ELSIF v_quest.reward_gold > 0 THEN
        -- Record gold-only quest reward transaction
        INSERT INTO inventory_transactions (
            player_id,
            item_id,
            transaction_type,
            quantity,
            gold_amount,
            description,
            created_at
        ) VALUES (
            NEW.player_id,
            NULL,
            'quest_reward',
            1,
            v_quest.reward_gold,
            'Reward for completing Quest #' || NEW.quest_id || ': ' || v_quest.title,
            NOW()
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_reward_quest_completion ON player_quests;
CREATE TRIGGER trg_reward_quest_completion
AFTER UPDATE OF status ON player_quests
FOR EACH ROW
WHEN (OLD.status IS DISTINCT FROM NEW.status AND NEW.status = 'completed')
EXECUTE FUNCTION fn_reward_quest_completion();


-- ----------------------------------------------------------------------------
-- TRIGGER F: NPC Affinity Interaction Timestamp Auto-Updater
-- Event: BEFORE INSERT OR UPDATE OF interaction_count ON npc_relationships
-- Action: Sets last_interaction to NOW() whenever a new relationship is created
--         or when interaction_count increments.
-- Note: Implemented as BEFORE trigger to optimize performance and prevent recursive
--       trigger firings.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_update_npc_last_interaction()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_interaction := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_update_npc_last_interaction ON npc_relationships;
CREATE TRIGGER trg_update_npc_last_interaction
BEFORE INSERT OR UPDATE OF interaction_count ON npc_relationships
FOR EACH ROW
EXECUTE FUNCTION fn_update_npc_last_interaction();


-- ----------------------------------------------------------------------------
-- TRIGGER G: Auto Level-Up Calculation on XP Progression
-- Event: BEFORE INSERT OR UPDATE OF xp ON players
-- Action: Automatically calculates player level dynamically from accumulated XP.
-- ----------------------------------------------------------------------------
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
