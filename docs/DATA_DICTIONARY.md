# Comprehensive Data Dictionary

This document serves as the canonical Data Dictionary for the **Generative NPC Memory Engine**. It provides complete technical specifications for all 10 relational tables, 3 analytical database views, relational indexes, and the Qdrant vector memory payload schema.

---

## 1. Relational Database Tables (PostgreSQL)

### 1.1 Table: `players`
**Description**: Stores registered player accounts, credentials, role-based authorization levels, progression metrics, and gold balances.

| Column Name | Data Type | Constraints | Default | Description |
|---|---|---|---|---|
| `player_id` | `INTEGER` | `GENERATED ALWAYS AS IDENTITY`, `PRIMARY KEY` | — | Unique internal surrogate key for the player account. |
| `username` | `VARCHAR(50)` | `NOT NULL`, `UNIQUE` | — | Player unique login and display name. Max 50 chars. |
| `email` | `VARCHAR(255)` | `NOT NULL`, `UNIQUE` | — | Validated unique email address for communication and security. |
| `password_hash` | `VARCHAR(255)` | `NOT NULL` | — | Bcrypt cryptographic hash string including salt and work factor. |
| `role` | `VARCHAR(20)` | `NOT NULL`, `CHECK (role IN ('player', 'admin'))` | `'player'` | Access control tier used for RBAC and authorization checks. |
| `gold` | `INTEGER` | `NOT NULL`, `CHECK (gold >= 0)` | `100` | Current wallet balance. CHECK constraint prevents negative gold. |
| `level` | `INTEGER` | `NOT NULL`, `CHECK (level > 0)` | `1` | Progression level of the character. Minimum value is 1. |
| `xp` | `INTEGER` | `NOT NULL`, `CHECK (xp >= 0)` | `0` | Cumulative experience points accrued across completed quests. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL` | `NOW()` | ISO timestamp representing account registration time. |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL` | `NOW()` | Timestamp representing the most recent profile update. |

---

### 1.2 Table: `npcs`
**Description**: Maintains definitions of non-player characters, their core behavioral personas, geographic locations, and personality configurations.

| Column Name | Data Type | Constraints | Default | Description |
|---|---|---|---|---|
| `npc_id` | `INTEGER` | `GENERATED ALWAYS AS IDENTITY`, `PRIMARY KEY` | — | Unique internal surrogate key identifying the NPC. |
| `name` | `VARCHAR(100)` | `NOT NULL`, `UNIQUE` | — | Unique canonical name of the NPC (e.g., 'Elric the Blacksmith'). |
| `persona` | `TEXT` | `NOT NULL` | — | Comprehensive system prompt describing character backstory, demeanor, and speech style. |
| `location` | `VARCHAR(100)` | `NULLABLE` | — | World settlement or zone name where the NPC resides. |
| `personality_traits` | `JSONB` | `NOT NULL` | `'{}'` | Key-value pairs of personality axes (e.g., `{"warmth": 0.8, "stoicism": 0.4}`). |
| `greeting` | `TEXT` | `NULLABLE` | — | Default introductory greeting spoken upon initial encounter. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL` | `NOW()` | Creation timestamp of the NPC record. |

---

### 1.3 Table: `items`
**Description**: Master inventory catalog containing available equipment, potions, weapons, armor, and quest items.

| Column Name | Data Type | Constraints | Default | Description |
|---|---|---|---|---|
| `item_id` | `INTEGER` | `GENERATED ALWAYS AS IDENTITY`, `PRIMARY KEY` | — | Unique surrogate identifier for the item catalog row. |
| `name` | `VARCHAR(100)` | `NOT NULL`, `UNIQUE` | — | Unique item name. |
| `description` | `TEXT` | `NULLABLE` | — | Flavour text, lore, and descriptive stat summary. |
| `base_price` | `INTEGER` | `NOT NULL`, `CHECK (base_price > 0)` | — | Base purchase price in gold units. Must be strictly positive. |
| `item_type` | `VARCHAR(50)` | `NOT NULL`, `CHECK (item_type IN ('weapon', 'armor', 'potion', 'misc', 'quest_item'))` | `'misc'` | Broad item category used for UI categorization and usage logic. |
| `rarity` | `VARCHAR(20)` | `NOT NULL`, `CHECK (rarity IN ('common', 'uncommon', 'rare', 'epic', 'legendary'))` | `'common'` | Quality tier determining drop scarcity and UI styling. |
| `stock` | `INTEGER` | `NOT NULL` | `-1` | Available merchant stock count. `-1` denotes infinite vendor stock. |
| `search_vector` | `TSVECTOR` | `NULLABLE` | — | Precomputed text search vector derived from `name` and `description`. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL` | `NOW()` | Timestamp when item was introduced into the catalog. |

---

### 1.4 Table: `quests`
**Description**: Stores quest definitions, completion rewards, minimum level gates, and full-text search indexing vectors.

| Column Name | Data Type | Constraints | Default | Description |
|---|---|---|---|---|
| `quest_id` | `INTEGER` | `GENERATED ALWAYS AS IDENTITY`, `PRIMARY KEY` | — | Unique surrogate identifier for the quest. |
| `title` | `VARCHAR(150)` | `NOT NULL`, `UNIQUE` | — | Unique descriptive title of the quest. |
| `description` | `TEXT` | `NOT NULL` | — | Full briefing of quest narrative, goals, and lore context. |
| `reward_gold` | `INTEGER` | `NOT NULL`, `CHECK (reward_gold >= 0)` | `0` | Gold awarded upon successful quest completion. |
| `reward_xp` | `INTEGER` | `NOT NULL`, `CHECK (reward_xp >= 0)` | `0` | Experience points awarded upon successful quest completion. |
| `reward_item_id` | `INTEGER` | `NULLABLE`, `FOREIGN KEY REFERENCES items(item_id) ON DELETE SET NULL` | `NULL` | Optional bonus item granted upon quest completion. |
| `min_level` | `INTEGER` | `NOT NULL`, `CHECK (min_level >= 1)` | `1` | Minimum player level required to accept the quest. |
| `quest_type` | `VARCHAR(50)` | `NOT NULL`, `CHECK (quest_type IN ('main', 'side', 'daily', 'bounty'))` | `'side'` | Gameplay category of the quest. |
| `search_vector` | `TSVECTOR` | `NULLABLE` | — | Precomputed text search vector derived from `title` and `description`. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL` | `NOW()` | Timestamp when quest definition was created. |

---

### 1.5 Table: `player_inventory`
**Description**: Associative junction table resolving the many-to-many relationship between players and items in their possession.

| Column Name | Data Type | Constraints | Default | Description |
|---|---|---|---|---|
| `inventory_id` | `INTEGER` | `GENERATED ALWAYS AS IDENTITY`, `PRIMARY KEY` | — | Unique surrogate key for the inventory slot entry. |
| `player_id` | `INTEGER` | `NOT NULL`, `FOREIGN KEY REFERENCES players(player_id) ON DELETE CASCADE` | — | Player owning this inventory slot. |
| `item_id` | `INTEGER` | `NOT NULL`, `FOREIGN KEY REFERENCES items(item_id) ON DELETE RESTRICT` | — | Catalog item held in this slot. Cannot delete item while held. |
| `quantity` | `INTEGER` | `NOT NULL`, `CHECK (quantity > 0)` | `1` | Count of this item held by player. CHECK constraint disallows `<= 0`. |
| `acquired_at` | `TIMESTAMPTZ` | `NOT NULL` | `NOW()` | Timestamp when player initially acquired this item stack. |

- **Table Constraints**:
  - `CONSTRAINT uq_player_inventory UNIQUE (player_id, item_id)`

---

### 1.6 Table: `player_quests`
**Description**: Tracks individual player progress, status transitions, and lifecycle timestamps for quests.

| Column Name | Data Type | Constraints | Default | Description |
|---|---|---|---|---|
| `player_quest_id` | `INTEGER` | `GENERATED ALWAYS AS IDENTITY`, `PRIMARY KEY` | — | Unique surrogate key for the quest progress record. |
| `player_id` | `INTEGER` | `NOT NULL`, `FOREIGN KEY REFERENCES players(player_id) ON DELETE CASCADE` | — | Referencing player undertaking the quest. |
| `quest_id` | `INTEGER` | `NOT NULL`, `FOREIGN KEY REFERENCES quests(quest_id) ON DELETE CASCADE` | — | Referencing quest being tracked. |
| `status` | `VARCHAR(20)` | `NOT NULL`, `CHECK (status IN ('not_started', 'in_progress', 'completed', 'failed'))` | `'in_progress'` | Current state of the quest for this player. |
| `started_at` | `TIMESTAMPTZ` | `NOT NULL` | `NOW()` | Timestamp when quest was accepted. |
| `completed_at` | `TIMESTAMPTZ` | `NULLABLE` | `NULL` | Timestamp when marked as completed or failed. |

- **Table Constraints**:
  - `CONSTRAINT uq_player_quest UNIQUE (player_id, quest_id)`

---

### 1.7 Table: `quest_prerequisites`
**Description**: Self-referencing Directed Acyclic Graph (DAG) defining dependency relationships between prerequisite and target quests.

| Column Name | Data Type | Constraints | Default | Description |
|---|---|---|---|---|
| `prerequisite_id` | `INTEGER` | `GENERATED ALWAYS AS IDENTITY`, `PRIMARY KEY` | — | Unique surrogate key for the prerequisite edge. |
| `quest_id` | `INTEGER` | `NOT NULL`, `FOREIGN KEY REFERENCES quests(quest_id) ON DELETE CASCADE` | — | Downstream target quest that requires unlocking. |
| `required_quest_id` | `INTEGER` | `NOT NULL`, `FOREIGN KEY REFERENCES quests(quest_id) ON DELETE RESTRICT` | — | Upstream prerequisite quest that must be completed first. |

- **Table Constraints**:
  - `CONSTRAINT uq_quest_prerequisite UNIQUE (quest_id, required_quest_id)`
  - `CONSTRAINT chk_no_self_prerequisite CHECK (quest_id <> required_quest_id)`

---

### 1.8 Table: `inventory_transactions`
**Description**: Immutable double-entry financial and item movement ledger recording all acquisitions, sales, and rewards.

| Column Name | Data Type | Constraints | Default | Description |
|---|---|---|---|---|
| `transaction_id` | `INTEGER` | `GENERATED ALWAYS AS IDENTITY`, `PRIMARY KEY` | — | Unique identifier for the ledger entry. |
| `player_id` | `INTEGER` | `NOT NULL`, `FOREIGN KEY REFERENCES players(player_id) ON DELETE CASCADE` | — | Referencing player executing or receiving the transaction. |
| `item_id` | `INTEGER` | `NOT NULL`, `FOREIGN KEY REFERENCES items(item_id) ON DELETE RESTRICT` | — | Catalog item transacted in this entry. |
| `transaction_type` | `VARCHAR(20)` | `NOT NULL`, `CHECK (transaction_type IN ('buy', 'sell', 'quest_reward', 'admin_grant'))` | — | Business classification of the transaction event. |
| `quantity` | `INTEGER` | `NOT NULL` | — | Net quantity change (+ for additions, - for deductions). |
| `gold_amount` | `INTEGER` | `NOT NULL` | — | Net gold currency delta (- for expenditure, + for sales/rewards). |
| `description` | `VARCHAR(255)` | `NULLABLE` | — | Explanatory context string. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL` | `NOW()` | Timestamp when transaction was permanently recorded. |

---

### 1.9 Table: `npc_relationships`
**Description**: Tracks dynamic social bonds, affinity scores, and interaction counts between players and NPCs.

| Column Name | Data Type | Constraints | Default | Description |
|---|---|---|---|---|
| `relationship_id` | `INTEGER` | `GENERATED ALWAYS AS IDENTITY`, `PRIMARY KEY` | — | Unique surrogate identifier for the social relationship. |
| `player_id` | `INTEGER` | `NOT NULL`, `FOREIGN KEY REFERENCES players(player_id) ON DELETE CASCADE` | — | Referencing player entity. |
| `npc_id` | `INTEGER` | `NOT NULL`, `FOREIGN KEY REFERENCES npcs(npc_id) ON DELETE CASCADE` | — | Referencing NPC entity. |
| `affinity_score` | `NUMERIC(5,2)` | `NOT NULL`, `CHECK (affinity_score >= -100.00 AND affinity_score <= 100.00)` | `0.00` | Sentiment score ranging between `-100.00` (hostile) to `+100.00` (revered). |
| `interaction_count` | `INTEGER` | `NOT NULL`, `CHECK (interaction_count >= 0)` | `0` | Total number of chat messages exchanged with this NPC. |
| `last_interaction` | `TIMESTAMPTZ` | `NOT NULL` | `NOW()` | Timestamp of the most recent conversation session. |

- **Table Constraints**:
  - `CONSTRAINT uq_player_npc UNIQUE (player_id, npc_id)`

---

### 1.10 Table: `audit_log`
**Description**: Autonomous Change Data Capture (CDC) table populated by trigger routines recording historical mutation deltas.

| Column Name | Data Type | Constraints | Default | Description |
|---|---|---|---|---|
| `log_id` | `INTEGER` | `GENERATED ALWAYS AS IDENTITY`, `PRIMARY KEY` | — | Unique surrogate identifier for the audit entry. |
| `table_name` | `VARCHAR(50)` | `NOT NULL` | — | Source database table subjected to modification. |
| `operation` | `VARCHAR(10)` | `NOT NULL`, `CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE'))` | — | DML operation type executed. |
| `row_id` | `INTEGER` | `NOT NULL` | — | Primary key identifier of the modified row. |
| `old_data` | `JSONB` | `NULLABLE` | — | Complete serialized JSON row snapshot before update/delete. |
| `new_data` | `JSONB` | `NULLABLE` | — | Complete serialized JSON row snapshot after insert/update. |
| `changed_by` | `VARCHAR(50)` | `NOT NULL` | `CURRENT_USER` | System user or database role responsible for execution. |
| `changed_at` | `TIMESTAMPTZ` | `NOT NULL` | `NOW()` | Timestamp when audit trigger fired. |

---

## 2. Database Views

### 2.1 View: `player_leaderboard`
**Purpose**: Computes real-time competitive rankings across all players based on character level, experience points, liquid gold currency, and total inventory wealth.

```sql
CREATE OR REPLACE VIEW player_leaderboard AS
SELECT 
    p.player_id,
    p.username,
    p.level,
    p.xp,
    p.gold,
    COALESCE(SUM(pi.quantity * i.base_price), 0) AS inventory_value,
    (p.gold + COALESCE(SUM(pi.quantity * i.base_price), 0)) AS total_net_worth,
    COUNT(DISTINCT pq.quest_id) FILTER (WHERE pq.status = 'completed') AS completed_quests_count,
    DENSE_RANK() OVER (ORDER BY p.level DESC, p.xp DESC, (p.gold + COALESCE(SUM(pi.quantity * i.base_price), 0)) DESC) AS ranking
FROM players p
LEFT JOIN player_inventory pi ON p.player_id = pi.player_id
LEFT JOIN items i ON pi.item_id = i.item_id
LEFT JOIN player_quests pq ON p.player_id = pq.player_id
GROUP BY p.player_id, p.username, p.level, p.xp, p.gold;
```

### 2.2 View: `npc_popularity`
**Purpose**: Summarizes conversational engagement, unique player outreach, average affinity sentiment, and highest affinity recorded per NPC.

```sql
CREATE OR REPLACE VIEW npc_popularity AS
SELECT 
    n.npc_id,
    n.name AS npc_name,
    n.location,
    COUNT(DISTINCT nr.player_id) AS total_unique_players,
    COALESCE(SUM(nr.interaction_count), 0) AS total_dialogue_turns,
    ROUND(COALESCE(AVG(nr.affinity_score), 0.00), 2) AS average_affinity,
    COALESCE(MAX(nr.affinity_score), 0.00) AS peak_affinity,
    COALESCE(MIN(nr.affinity_score), 0.00) AS lowest_affinity
FROM npcs n
LEFT JOIN npc_relationships nr ON n.npc_id = nr.npc_id
GROUP BY n.npc_id, n.name, n.location
ORDER BY total_dialogue_turns DESC;
```

### 2.3 View: `quest_progress`
**Purpose**: Provides administrative and analytical visibility into quest completion velocity, active participant rates, and failure ratios.

```sql
CREATE OR REPLACE VIEW quest_progress AS
SELECT 
    q.quest_id,
    q.title AS quest_title,
    q.quest_type,
    q.min_level,
    q.reward_gold,
    q.reward_xp,
    COUNT(pq.player_quest_id) AS total_enrolled_players,
    COUNT(pq.player_quest_id) FILTER (WHERE pq.status = 'in_progress') AS active_count,
    COUNT(pq.player_quest_id) FILTER (WHERE pq.status = 'completed') AS completed_count,
    COUNT(pq.player_quest_id) FILTER (WHERE pq.status = 'failed') AS failed_count,
    CASE 
        WHEN COUNT(pq.player_quest_id) > 0 
        THEN ROUND((COUNT(pq.player_quest_id) FILTER (WHERE pq.status = 'completed')::NUMERIC / COUNT(pq.player_quest_id)::NUMERIC) * 100.0, 1)
        ELSE 0.0 
    END AS completion_percentage
FROM quests q
LEFT JOIN player_quests pq ON q.quest_id = pq.quest_id
GROUP BY q.quest_id, q.title, q.quest_type, q.min_level, q.reward_gold, q.reward_xp
ORDER BY q.min_level ASC, total_enrolled_players DESC;
```

---

## 3. Qdrant Vector Collection: `npc_memories`

**Description**: High-dimensional vector space storing conversational utterances, distilled memories, and dialogue exchanges between players and NPCs.

### 3.1 Vector Configuration
- **Collection**: `npc_memories`
- **Vector Dimension**: `384` float scalars
- **Distance Metric**: `Cosine`
- **HNSW Parameters**: `m = 16`, `ef_construct = 100`, `on_disk = false`

### 3.2 Payload Fields Specification

| Field Name | Type | Qdrant Index | Required | Example | Description |
|---|---|---|---|---|---|
| `player_id` | `integer` | `integer` | Yes | `1` | Referencing player account ID in PostgreSQL. Used for strict isolation filtering. |
| `npc_id` | `integer` | `integer` | Yes | `2` | Referencing NPC entity ID in PostgreSQL. Used for character-specific filtering. |
| `session_id` | `string` | `keyword` | Yes | `"c7a9e320-11fa-4f9e-a812-78d10b7b1291"` | Session identifier grouping continuous conversation interactions. |
| `text` | `string` | Full-text | Yes | `"The player mentioned searching for the legendary Moonlit Dagger."` | Raw utterance text or summarized episodic memory observation. |
| `role` | `string` | `keyword` | Yes | `"player"` | Speaker role classification: `"player"` or `"npc"`. |
| `importance` | `float` | `float` | Yes | `0.85` | Importance weight between `0.0` (trivial greeting) and `1.0` (critical quest secret). |
| `timestamp` | `float` | `float` | Yes | `1730304000.0` | Unix epoch timestamp indicating creation time for recency calculations. |
| `emotion` | `string` | `keyword` | No | `"curious"` | Dominant emotion detected during dialogue (e.g., `"friendly"`, `"hostile"`). |

---

## 4. PostgreSQL Indexes Summary

| Target Table | Index Name | Type | Indexed Columns | Justification / Usage |
|---|---|---|---|---|
| `players` | `idx_players_username` | B-tree | `username` | Enforces instant $\mathcal{O}(\log N)$ authentication lookups during login. |
| `players` | `idx_players_email` | B-tree | `email` | Rapid duplicate check on registration. |
| `items` | `idx_items_search_vector`| GIN | `search_vector` | Accelerates full-text search queries using `@@ to_tsquery()`. |
| `quests` | `idx_quests_search_vector`| GIN | `search_vector` | Accelerates quest full-text discovery. |
| `player_inventory` | `idx_player_inventory_player`| B-tree | `player_id` | Optimizes player bag lookups and RLS policy enforcement. |
| `player_inventory` | `idx_player_inventory_item` | B-tree | `item_id` | Accelerates cascade checks and RESTRICT foreign key joins. |
| `player_quests` | `idx_player_quests_player`| B-tree | `player_id` | Speeds up active quest listings for a given player. |
| `quest_prerequisites`| `idx_quest_prereq_graph` | B-tree | `quest_id, required_quest_id` | Optimizes recursive CTE traversal for prerequisite graph evaluation. |
| `inventory_transactions`| `idx_inv_tx_player_created`| B-tree | `player_id, created_at DESC` | Powers paginated transaction history queries for the player dashboard. |
| `npc_relationships` | `idx_npc_rel_lookup` | B-tree | `player_id, npc_id` | Sub-millisecond affinity and interaction retrieval during chat fusion. |
| `audit_log` | `idx_audit_log_table_row` | B-tree | `table_name, row_id` | Administrative inspection of row audit history. |
