-- ============================================================================
-- Generative NPC Memory Engine - Comprehensive Demonstration SQL Queries
-- Project: Generative NPC Memory Engine (PES University DBMS Mini-Project)
-- File: db/demo_queries.sql
-- Description: Rigorous collection of demonstration queries illustrating advanced
--              SQL constructs, multi-table joins, recursive CTEs, window functions,
--              full-text search, subqueries, and ACID-compliant DML mutations.
-- Rubric Criteria: Comprehensive Query Demonstration (A through N)
-- ============================================================================

-- ============================================================================
-- QUERY A: Multi-Table JOIN
-- Rubric: Multi-Table Joins, Computed Columns, Window Aggregations
-- Description: Joins players, player_inventory, and items to compute individual
--              item valuation and overall inventory wealth per player.
-- ============================================================================
SELECT 
    p.player_id,
    p.username,
    i.item_id,
    i.name AS item_name,
    i.rarity,
    pi.quantity,
    i.base_price AS unit_price,
    (pi.quantity * i.base_price) AS line_item_value,
    SUM(pi.quantity * i.base_price) OVER (PARTITION BY p.player_id) AS total_inventory_worth
FROM players p
JOIN player_inventory pi ON p.player_id = pi.player_id
JOIN items i ON pi.item_id = i.item_id
ORDER BY p.player_id ASC, line_item_value DESC;


-- ============================================================================
-- QUERY B: LEFT JOIN
-- Rubric: Outer Joins, Preserving Unmatched Left Tuples, Handling Nullability
-- Description: Returns all quests regardless of whether they have prerequisites,
--              resolving prerequisite titles or providing a fallback indicator.
-- ============================================================================
SELECT 
    q.quest_id,
    q.title AS quest_title,
    q.quest_type,
    q.min_level,
    qp.required_quest_id,
    COALESCE(rq.title, 'None (Starter Quest)') AS prerequisite_quest_title
FROM quests q
LEFT JOIN quest_prerequisites qp ON q.quest_id = qp.quest_id
LEFT JOIN quests rq ON qp.required_quest_id = rq.quest_id
ORDER BY q.quest_id ASC, qp.required_quest_id ASC NULLS FIRST;


-- ============================================================================
-- QUERY C: GROUP BY + HAVING
-- Rubric: Aggregation with Filtering on Aggregate Conditions
-- Description: Identifies players holding 2 or more distinct item types in
--              inventory, computing cumulative counts and asset valuations.
-- ============================================================================
SELECT 
    p.player_id,
    p.username,
    COUNT(pi.item_id) AS distinct_item_types,
    SUM(pi.quantity) AS total_item_units,
    SUM(pi.quantity * i.base_price) AS aggregate_valuation
FROM players p
JOIN player_inventory pi ON p.player_id = pi.player_id
JOIN items i ON pi.item_id = i.item_id
GROUP BY p.player_id, p.username
HAVING COUNT(pi.item_id) >= 2
ORDER BY total_item_units DESC;


-- ============================================================================
-- QUERY D: ORDER BY with Custom Priority Expression
-- Rubric: Complex Sorting, CASE Expression Ordering
-- Description: Sorts the item catalog according to a domain-specific rarity tier
--              hierarchy (Legendary > Epic > Rare > Uncommon > Common), sub-sorted by price.
-- ============================================================================
SELECT 
    item_id,
    name,
    item_type,
    rarity,
    base_price,
    stock
FROM items
ORDER BY 
    CASE rarity
        WHEN 'legendary' THEN 1
        WHEN 'epic'      THEN 2
        WHEN 'rare'      THEN 3
        WHEN 'uncommon'  THEN 4
        WHEN 'common'    THEN 5
        ELSE 6
    END ASC,
    base_price DESC;


-- ============================================================================
-- QUERY E: Nested Subquery
-- Rubric: Non-Correlated Subquery in WHERE Clause
-- Description: Identifies any player possessing the single most expensive item
--              in the database catalog.
-- ============================================================================
SELECT 
    p.player_id,
    p.username,
    p.level,
    i.item_id,
    i.name AS item_name,
    i.base_price,
    pi.quantity
FROM players p
JOIN player_inventory pi ON p.player_id = pi.player_id
JOIN items i ON pi.item_id = i.item_id
WHERE i.item_id = (
    SELECT item_id
    FROM items
    ORDER BY base_price DESC
    LIMIT 1
);


-- ============================================================================
-- QUERY F: Correlated Subquery
-- Rubric: Scalar Correlated Subqueries Referencing Outer Query Columns
-- Description: For every player, evaluates and projects the details of their
--              single most recent transaction from the ledger.
-- ============================================================================
SELECT 
    p.player_id,
    p.username,
    p.gold AS current_gold_reserve,
    (
        SELECT it.transaction_type || ' (' || it.quantity || ' items, ' || it.gold_amount || ' gold) on ' || it.created_at::DATE
        FROM inventory_transactions it
        WHERE it.player_id = p.player_id
        ORDER BY it.created_at DESC
        LIMIT 1
    ) AS most_recent_transaction
FROM players p
ORDER BY p.player_id ASC;


-- ============================================================================
-- QUERY G: Recursive Common Table Expression (CTE)
-- Rubric: Hierarchical Data Navigation, Directed Acyclic Graph (DAG) Traversal
-- Description: Traverses the complete multi-level prerequisite tree for Quest #8
--              ("Dragon's Awakening"), reporting recursion depth and path breadcrumbs.
-- ============================================================================
WITH RECURSIVE quest_tree AS (
    -- Anchor Member: Immediate direct prerequisites of Quest 8
    SELECT 
        qp.quest_id,
        q.title AS quest_title,
        qp.required_quest_id,
        req.title AS required_title,
        1 AS depth_level,
        ARRAY[q.title, req.title] AS dependency_breadcrumb
    FROM quest_prerequisites qp
    JOIN quests q ON qp.quest_id = q.quest_id
    JOIN quests req ON qp.required_quest_id = req.quest_id
    WHERE qp.quest_id = 8

    UNION ALL

    -- Recursive Member: Prerequisites of previous depth prerequisites
    SELECT 
        qp.quest_id,
        q.title AS quest_title,
        qp.required_quest_id,
        req.title AS required_title,
        qt.depth_level + 1 AS depth_level,
        qt.dependency_breadcrumb || req.title AS dependency_breadcrumb
    FROM quest_prerequisites qp
    JOIN quests q ON qp.quest_id = q.quest_id
    JOIN quests req ON qp.required_quest_id = req.quest_id
    JOIN quest_tree qt ON qp.quest_id = qt.required_quest_id
)
SELECT 
    depth_level,
    quest_id,
    quest_title,
    required_quest_id,
    required_title,
    array_to_string(dependency_breadcrumb, ' -> ') AS full_prerequisite_chain
FROM quest_tree
ORDER BY depth_level ASC, required_quest_id ASC;


-- ============================================================================
-- QUERY H: Window Functions (Partitioning and Ranking)
-- Rubric: Analytical Window Functions (RANK, DENSE_RANK, Windowed Averages)
-- Description: Computes within-level player wealth ranks, overall wealth ranks,
--              and average gold benchmarked against peers in the same level.
-- ============================================================================
SELECT 
    player_id,
    username,
    level,
    gold,
    xp,
    RANK() OVER (
        PARTITION BY level 
        ORDER BY gold DESC
    ) AS wealth_rank_within_level,
    DENSE_RANK() OVER (
        ORDER BY gold DESC
    ) AS global_wealth_rank,
    ROUND(AVG(gold) OVER (
        PARTITION BY level
    ), 2) AS average_gold_for_level
FROM players
ORDER BY level DESC, gold DESC;


-- ============================================================================
-- QUERY I: Full-Text Search (GIN Indexed)
-- Rubric: PostgreSQL Full-Text Search (to_tsquery, ts_rank, GIN Acceleration)
-- Description: Searches the items catalog using natural language lexemes with
--              boolean disjunction and relevance scoring.
-- ============================================================================
SELECT 
    item_id,
    name,
    description,
    item_type,
    rarity,
    base_price,
    ts_rank(search_vector, to_tsquery('english', 'steel | blade | dragon')) AS search_relevance
FROM items
WHERE search_vector @@ to_tsquery('english', 'steel | blade | dragon')
ORDER BY search_relevance DESC, base_price DESC;


-- ============================================================================
-- QUERY J: EXISTS / NOT EXISTS Subquery
-- Rubric: Semi-Joins and Anti-Joins using EXISTS Constructs
-- Description: Identifies high-tier quests that have not yet been marked as
--              'completed' by any player in the system.
-- ============================================================================
SELECT 
    q.quest_id,
    q.title,
    q.quest_type,
    q.min_level,
    q.reward_gold,
    q.reward_xp
FROM quests q
WHERE NOT EXISTS (
    SELECT 1
    FROM player_quests pq
    WHERE pq.quest_id = q.quest_id
      AND pq.status = 'completed'
)
ORDER BY q.min_level ASC, q.quest_id ASC;


-- ============================================================================
-- QUERY K: Aggregations and Financial Metrics
-- Rubric: Multi-Aggregate Summary Functions (SUM, AVG, COUNT, MAX)
-- Description: Computes cumulative expenditures, purchase transaction volume,
--              and average basket sizes for all players who bought items.
-- ============================================================================
SELECT 
    p.player_id,
    p.username,
    p.gold AS liquid_gold,
    COUNT(it.transaction_id) AS purchase_count,
    COALESCE(SUM(it.gold_amount), 0) AS total_gold_spent,
    COALESCE(ROUND(AVG(it.gold_amount), 2), 0.00) AS avg_purchase_amount,
    COALESCE(MAX(it.gold_amount), 0) AS max_single_purchase
FROM players p
LEFT JOIN inventory_transactions it 
    ON p.player_id = it.player_id AND it.transaction_type = 'buy'
GROUP BY p.player_id, p.username, p.gold
ORDER BY total_gold_spent DESC;


-- ============================================================================
-- QUERY L: UPDATE with Subquery
-- Rubric: Set-Oriented Data Mutation Guided by Correlated Subquery Filtering
-- Description: Rewards all players who have established a strong alliance
--              (affinity score >= 50.00) with any NPC by awarding a 50 gold stipend.
-- ============================================================================
UPDATE players
SET gold = gold + 50,
    updated_at = NOW()
WHERE player_id IN (
    SELECT DISTINCT nr.player_id
    FROM npc_relationships nr
    WHERE nr.affinity_score >= 50.00
);


-- ============================================================================
-- QUERY M: DELETE with Conditional Safety Predicates
-- Rubric: Data Teardown and Integrity Cleanup with Conditions
-- Description: Prunes exhausted inventory entries with zero quantity or orphaned
--              records without corresponding parent players.
-- ============================================================================
DELETE FROM player_inventory
WHERE quantity <= 0
   OR player_id NOT IN (SELECT player_id FROM players);


-- ============================================================================
-- QUERY N: INSERT ... ON CONFLICT (UPSERT)
-- Rubric: Atomic Upsert Operation, Conflict Resolution
-- Description: Atomically adds potions to a player's inventory, incrementing
--              existing quantity if already owned or inserting a new record.
-- ============================================================================
INSERT INTO player_inventory (player_id, item_id, quantity, acquired_at)
VALUES (2, 5, 2, NOW())
ON CONFLICT (player_id, item_id)
DO UPDATE SET 
    quantity = player_inventory.quantity + EXCLUDED.quantity,
    acquired_at = NOW()
RETURNING inventory_id, player_id, item_id, quantity, acquired_at;
