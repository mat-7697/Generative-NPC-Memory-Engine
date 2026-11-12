-- ============================================================================
-- Generative NPC Memory Engine - Relational Views
-- Project: Generative NPC Memory Engine (PES University DBMS Mini-Project)
-- File: db/views.sql
-- Description: Complex relational views encapsulating multi-table aggregations,
--              analytical window functions, and business metrics for player
--              rankings, NPC popularity sentiment, and quest progression tracking.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- VIEW 1: player_leaderboard
-- Description: Ranks players by level, XP, and gold reserves. Aggregates completed
--              quests and total inventory item count across all players.
-- Analytical Features: DENSE_RANK() window function, multi-table LEFT JOINs,
--                      scalar aggregations with COALESCE fallback.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW player_leaderboard AS
SELECT 
    p.player_id,
    p.username,
    p.level,
    p.xp,
    p.gold,
    COALESCE(qc.completed_quests, 0)::BIGINT AS quest_completion_count,
    COALESCE(inv.total_items, 0)::BIGINT AS total_items_owned,
    DENSE_RANK() OVER (
        ORDER BY p.level DESC, p.xp DESC, p.gold DESC
    ) AS leaderboard_rank
FROM players p
LEFT JOIN (
    SELECT player_id, COUNT(*) AS completed_quests
    FROM player_quests
    WHERE status = 'completed'
    GROUP BY player_id
) qc ON p.player_id = qc.player_id
LEFT JOIN (
    SELECT player_id, SUM(quantity) AS total_items
    FROM player_inventory
    GROUP BY player_id
) inv ON p.player_id = inv.player_id;

COMMENT ON VIEW player_leaderboard IS 'Leaderboard view displaying player standing, completed quests, and item totals';


-- ----------------------------------------------------------------------------
-- VIEW 2: npc_popularity
-- Description: Ranks NPCs by interaction volume and relational sentiment.
-- Metrics: Total unique players, total interaction count, average affinity score,
--          and relative popularity rank.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW npc_popularity AS
SELECT 
    n.npc_id,
    n.name AS npc_name,
    n.location,
    COUNT(DISTINCT nr.player_id)::BIGINT AS total_unique_players,
    COALESCE(SUM(nr.interaction_count), 0)::BIGINT AS total_interaction_count,
    COALESCE(ROUND(AVG(nr.affinity_score), 2), 0.00)::DECIMAL(5,2) AS avg_affinity_score,
    DENSE_RANK() OVER (
        ORDER BY COALESCE(SUM(nr.interaction_count), 0) DESC,
                 COALESCE(AVG(nr.affinity_score), 0) DESC
    ) AS popularity_rank
FROM npcs n
LEFT JOIN npc_relationships nr ON n.npc_id = nr.npc_id
GROUP BY n.npc_id, n.name, n.location;

COMMENT ON VIEW npc_popularity IS 'Aggregated analytics on NPC player engagement, sentiment affinity, and popularity ranks';


-- ----------------------------------------------------------------------------
-- VIEW 3: quest_progress
-- Description: Evaluates every player-quest pair in the engine. Displays quest
--              lifecycle status, rewards (gold, xp, items), and computes whether
--              all transitive DAG prerequisites and min_level criteria are met.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW quest_progress AS
SELECT 
    p.player_id,
    p.username,
    p.level AS player_level,
    q.quest_id,
    q.title AS quest_title,
    q.quest_type,
    q.min_level,
    COALESCE(pq.status, 'available') AS status,
    q.reward_gold,
    q.reward_xp,
    q.reward_item_id,
    i.name AS reward_item_name,
    can_start_quest(p.player_id, q.quest_id) AS prerequisites_met,
    pq.started_at,
    pq.completed_at
FROM players p
CROSS JOIN quests q
LEFT JOIN items i ON q.reward_item_id = i.item_id
LEFT JOIN player_quests pq ON p.player_id = pq.player_id AND q.quest_id = pq.quest_id;

COMMENT ON VIEW quest_progress IS 'Comprehensive matrix of player-quest statuses, rewards, and prerequisite eligibility';
