-- ============================================================================
-- Generative NPC Memory Engine - Stored Procedures & Functions
-- Project: Generative NPC Memory Engine (PES University DBMS Mini-Project)
-- File: db/procedures.sql
-- Description: Stored procedures and functions for ACID transactional commerce,
--              inventory transfers with deadlock prevention, recursive prerequisite
--              validation, and hierarchical prerequisite DAG traversal.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- PROCEDURE A: buy_item
-- Arguments: p_player_id INT, p_item_id INT, p_quantity INT
-- Description: Handles item purchases with pessimistic row locking (FOR UPDATE),
--              funds validation, stock decrementing, inventory upsert, and
--              transaction logging within an atomic transaction.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE buy_item(
    p_player_id INT,
    p_item_id INT,
    p_quantity INT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_player_gold INT;
    v_item_price INT;
    v_item_stock INT;
    v_item_name VARCHAR(100);
    v_total_cost INT;
BEGIN
    IF p_quantity <= 0 THEN
        RAISE EXCEPTION 'Purchase quantity must be greater than zero. Received: %', p_quantity;
    END IF;

    -- 1. Pessimistic lock on player row to prevent concurrent race condition spending
    SELECT gold INTO v_player_gold
    FROM players
    WHERE player_id = p_player_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player with ID % does not exist', p_player_id;
    END IF;

    -- 2. Pessimistic lock on item row to ensure accurate stock and pricing evaluation
    SELECT base_price, stock, name
    INTO v_item_price, v_item_stock, v_item_name
    FROM items
    WHERE item_id = p_item_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Item with ID % does not exist', p_item_id;
    END IF;

    -- 3. Calculate financial cost
    v_total_cost := v_item_price * p_quantity;

    -- 4. Check player solvency
    IF v_player_gold < v_total_cost THEN
        RAISE EXCEPTION 'Insufficient gold: Player has % gold, but % gold is required for %x %',
            v_player_gold, v_total_cost, p_quantity, v_item_name;
    END IF;

    -- 5. Check item stock availability (-1 signifies infinite merchant supply)
    IF v_item_stock != -1 AND v_item_stock < p_quantity THEN
        RAISE EXCEPTION 'Insufficient stock: Item "%" has % in stock, but % was requested',
            v_item_name, v_item_stock, p_quantity;
    END IF;

    -- 6. Deduct player gold
    UPDATE players
    SET gold = gold - v_total_cost,
        updated_at = NOW()
    WHERE player_id = p_player_id;

    -- 7. Deduct item stock if finite
    IF v_item_stock != -1 THEN
        UPDATE items
        SET stock = stock - p_quantity
        WHERE item_id = p_item_id;
    END IF;

    -- 8. Upsert player inventory record
    INSERT INTO player_inventory (player_id, item_id, quantity, acquired_at)
    VALUES (p_player_id, p_item_id, p_quantity, NOW())
    ON CONFLICT (player_id, item_id)
    DO UPDATE SET quantity = player_inventory.quantity + p_quantity;

    -- 9. Append transaction record into immutable audit ledger
    INSERT INTO inventory_transactions (
        player_id,
        item_id,
        transaction_type,
        quantity,
        gold_amount,
        description,
        created_at
    ) VALUES (
        p_player_id,
        p_item_id,
        'buy',
        p_quantity,
        v_total_cost,
        'Purchased ' || p_quantity || 'x "' || v_item_name || '" for ' || v_total_cost || ' gold',
        NOW()
    );
END;
$$;


-- ----------------------------------------------------------------------------
-- PROCEDURE B: sell_item
-- Arguments: p_player_id INT, p_item_id INT, p_quantity INT
-- Description: Sells player items at 50% base price with row locking, restores
--              merchant stock (if not infinite), deletes depleted inventory rows,
--              and logs transaction.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE sell_item(
    p_player_id INT,
    p_item_id INT,
    p_quantity INT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_inv_quantity INT;
    v_item_price INT;
    v_item_stock INT;
    v_item_name VARCHAR(100);
    v_unit_sell_price INT;
    v_total_gold INT;
BEGIN
    IF p_quantity <= 0 THEN
        RAISE EXCEPTION 'Sale quantity must be greater than zero. Received: %', p_quantity;
    END IF;

    -- 1. Pessimistic lock on player row
    PERFORM 1 FROM players WHERE player_id = p_player_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player with ID % does not exist', p_player_id;
    END IF;

    -- 2. Pessimistic lock on player inventory row
    SELECT quantity INTO v_inv_quantity
    FROM player_inventory
    WHERE player_id = p_player_id AND item_id = p_item_id
    FOR UPDATE;

    IF NOT FOUND OR v_inv_quantity < p_quantity THEN
        RAISE EXCEPTION 'Insufficient inventory: Player has % of item ID %, requested to sell %',
            COALESCE(v_inv_quantity, 0), p_item_id, p_quantity;
    END IF;

    -- 3. Pessimistic lock on item row
    SELECT base_price, stock, name
    INTO v_item_price, v_item_stock, v_item_name
    FROM items
    WHERE item_id = p_item_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Item with ID % does not exist', p_item_id;
    END IF;

    -- 4. Calculate vendor buyback price (50% of base value, minimum 1 gold)
    v_unit_sell_price := GREATEST(1, FLOOR(v_item_price * 0.5));
    v_total_gold := v_unit_sell_price * p_quantity;

    -- 5. Credit gold to player
    UPDATE players
    SET gold = gold + v_total_gold,
        updated_at = NOW()
    WHERE player_id = p_player_id;

    -- 6. Decrement inventory or delete record if depleted to 0
    IF v_inv_quantity = p_quantity THEN
        DELETE FROM player_inventory
        WHERE player_id = p_player_id AND item_id = p_item_id;
    ELSE
        UPDATE player_inventory
        SET quantity = quantity - p_quantity
        WHERE player_id = p_player_id AND item_id = p_item_id;
    END IF;

    -- 7. Replenish merchant stock if tracked
    IF v_item_stock != -1 THEN
        UPDATE items
        SET stock = stock + p_quantity
        WHERE item_id = p_item_id;
    END IF;

    -- 8. Write to inventory_transactions
    INSERT INTO inventory_transactions (
        player_id,
        item_id,
        transaction_type,
        quantity,
        gold_amount,
        description,
        created_at
    ) VALUES (
        p_player_id,
        p_item_id,
        'sell',
        p_quantity,
        v_total_gold,
        'Sold ' || p_quantity || 'x "' || v_item_name || '" for ' || v_total_gold || ' gold',
        NOW()
    );
END;
$$;


-- ----------------------------------------------------------------------------
-- PROCEDURE C: transfer_item
-- Arguments: p_from_player_id INT, p_to_player_id INT, p_item_id INT, p_quantity INT
-- Description: Transfers items between two players with deadlock avoidance
--              via ordered key locking, validates sender balances, upserts recipient
--              inventory, and writes double-entry ledger transactions.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE transfer_item(
    p_from_player_id INT,
    p_to_player_id INT,
    p_item_id INT,
    p_quantity INT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_first_lock_id INT;
    v_second_lock_id INT;
    v_sender_qty INT;
    v_item_name VARCHAR(100);
BEGIN
    IF p_from_player_id = p_to_player_id THEN
        RAISE EXCEPTION 'Sender and receiver cannot be the same player (ID: %)', p_from_player_id;
    END IF;

    IF p_quantity <= 0 THEN
        RAISE EXCEPTION 'Transfer quantity must be greater than zero. Received: %', p_quantity;
    END IF;

    -- 1. Deadlock Prevention Strategy: Lock player accounts in strictly ascending primary key order
    v_first_lock_id := LEAST(p_from_player_id, p_to_player_id);
    v_second_lock_id := GREATEST(p_from_player_id, p_to_player_id);

    PERFORM 1 FROM players WHERE player_id = v_first_lock_id FOR UPDATE;
    PERFORM 1 FROM players WHERE player_id = v_second_lock_id FOR UPDATE;

    -- 2. Verify target item validity
    SELECT name INTO v_item_name FROM items WHERE item_id = p_item_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Item with ID % does not exist', p_item_id;
    END IF;

    -- 3. Lock and verify sender's inventory balance
    SELECT quantity INTO v_sender_qty
    FROM player_inventory
    WHERE player_id = p_from_player_id AND item_id = p_item_id
    FOR UPDATE;

    IF NOT FOUND OR v_sender_qty < p_quantity THEN
        RAISE EXCEPTION 'Insufficient quantity: Sender % possesses % of item %, requested %',
            p_from_player_id, COALESCE(v_sender_qty, 0), p_item_id, p_quantity;
    END IF;

    -- 4. Deduct or remove sender inventory
    IF v_sender_qty = p_quantity THEN
        DELETE FROM player_inventory
        WHERE player_id = p_from_player_id AND item_id = p_item_id;
    ELSE
        UPDATE player_inventory
        SET quantity = quantity - p_quantity
        WHERE player_id = p_from_player_id AND item_id = p_item_id;
    END IF;

    -- 5. Credit recipient inventory (Upsert)
    INSERT INTO player_inventory (player_id, item_id, quantity, acquired_at)
    VALUES (p_to_player_id, p_item_id, p_quantity, NOW())
    ON CONFLICT (player_id, item_id)
    DO UPDATE SET quantity = player_inventory.quantity + p_quantity;

    -- 6. Log transfer_out for sender
    INSERT INTO inventory_transactions (
        player_id,
        item_id,
        transaction_type,
        quantity,
        gold_amount,
        description,
        created_at
    ) VALUES (
        p_from_player_id,
        p_item_id,
        'transfer_out',
        p_quantity,
        0,
        'Transferred ' || p_quantity || 'x "' || v_item_name || '" to Player #' || p_to_player_id,
        NOW()
    );

    -- 7. Log transfer_in for receiver
    INSERT INTO inventory_transactions (
        player_id,
        item_id,
        transaction_type,
        quantity,
        gold_amount,
        description,
        created_at
    ) VALUES (
        p_to_player_id,
        p_item_id,
        'transfer_in',
        p_quantity,
        0,
        'Received ' || p_quantity || 'x "' || v_item_name || '" from Player #' || p_from_player_id,
        NOW()
    );
END;
$$;


-- ----------------------------------------------------------------------------
-- FUNCTION D: can_start_quest
-- Arguments: p_player_id INT, p_quest_id INT
-- Returns: BOOLEAN
-- Description: Recursively navigates the prerequisite DAG to ensure that
--              all ancestor quests are marked 'completed' by the player,
--              and verifies the player satisfies min_level.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION can_start_quest(
    p_player_id INT,
    p_quest_id INT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_player_level INT;
    v_min_level INT;
    v_unmet_prereqs INT;
BEGIN
    -- 1. Verify player existence and level
    SELECT level INTO v_player_level FROM players WHERE player_id = p_player_id;
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- 2. Verify quest existence and level gate
    SELECT min_level INTO v_min_level FROM quests WHERE quest_id = p_quest_id;
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    IF v_player_level < v_min_level THEN
        RETURN FALSE;
    END IF;

    -- 3. Recursive Common Table Expression (CTE) to resolve transitive prerequisite dependencies
    WITH RECURSIVE prereq_tree AS (
        -- Anchor: Immediate prerequisites of target quest
        SELECT required_quest_id
        FROM quest_prerequisites
        WHERE quest_id = p_quest_id

        UNION

        -- Recursive step: Prerequisites of prerequisites
        SELECT qp.required_quest_id
        FROM quest_prerequisites qp
        INNER JOIN prereq_tree pt ON qp.quest_id = pt.required_quest_id
    )
    -- Determine if any prerequisite quest remains incomplete
    SELECT COUNT(*)
    INTO v_unmet_prereqs
    FROM prereq_tree pt
    WHERE NOT EXISTS (
        SELECT 1
        FROM player_quests pq
        WHERE pq.player_id = p_player_id
          AND pq.quest_id = pt.required_quest_id
          AND pq.status = 'completed'
    );

    RETURN (v_unmet_prereqs = 0);
END;
$$;


-- ----------------------------------------------------------------------------
-- FUNCTION E: get_prerequisite_chain
-- Arguments: p_quest_id INT
-- Returns: TABLE (quest_id, quest_title, required_quest_id, required_quest_title, depth, prerequisite_path)
-- Description: Returns the full hierarchical prerequisite dependency tree with
--              recursion depth and human-readable dependency breadcrumb paths.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION get_prerequisite_chain(p_quest_id INT)
RETURNS TABLE (
    quest_id INT,
    quest_title VARCHAR(200),
    required_quest_id INT,
    required_quest_title VARCHAR(200),
    depth INT,
    prerequisite_path TEXT
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE chain AS (
        -- Anchor Member: Direct prerequisites at depth 1
        SELECT 
            qp.quest_id,
            q.title AS quest_title,
            qp.required_quest_id,
            rq.title AS required_quest_title,
            1 AS depth,
            q.title || ' -> ' || rq.title AS prerequisite_path
        FROM quest_prerequisites qp
        JOIN quests q ON qp.quest_id = q.quest_id
        JOIN quests rq ON qp.required_quest_id = rq.quest_id
        WHERE qp.quest_id = p_quest_id

        UNION ALL

        -- Recursive Member: Deeper prerequisite chain traversal
        SELECT 
            qp.quest_id,
            q.title AS quest_title,
            qp.required_quest_id,
            rq.title AS required_quest_title,
            c.depth + 1 AS depth,
            c.prerequisite_path || ' -> ' || rq.title AS prerequisite_path
        FROM quest_prerequisites qp
        JOIN quests q ON qp.quest_id = q.quest_id
        JOIN quests rq ON qp.required_quest_id = rq.quest_id
        JOIN chain c ON qp.quest_id = c.required_quest_id
    )
    SELECT 
        c.quest_id,
        c.quest_title,
        c.required_quest_id,
        c.required_quest_title,
        c.depth,
        c.prerequisite_path
    FROM chain c
    ORDER BY c.depth ASC, c.required_quest_id ASC;
END;
$$;
