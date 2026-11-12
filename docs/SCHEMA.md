# Relational & Vector Schema Specification

This document details the relational database schema implemented in **PostgreSQL 16+** and the vector database collection configured in **Qdrant**. The architecture provides strict ACID integrity for transactional gameplay while enabling semantic nearest-neighbor retrieval for generative NPC dialogues.

---

## 1. PostgreSQL Relational Tables

### 1.1 `players`
Represents player credentials, global account configuration, progression attributes, and liquid currency balance.

| Column Name | Data Type | Constraints | Default | Description |
|---|---|---|---|---|
| `player_id` | `INTEGER` | `GENERATED ALWAYS AS IDENTITY`, `PRIMARY KEY` | — | Unique surrogate identifier for the player. |
| `username` | `VARCHAR(50)` | `NOT NULL`, `UNIQUE` | — | Unique alphanumeric player handle. |
| `email` | `VARCHAR(255)` | `NOT NULL`, `UNIQUE` | — | Player email address for account recovery. |
| `password_hash` | `VARCHAR(255)` | `NOT NULL` | — | Cryptographic hash (Bcrypt blowfish format). |
| `role` | `VARCHAR(20)` | `NOT NULL`, `CHECK (role IN ('player', 'admin'))` | `'player'` | Application and database authorization role. |
| `gold` | `INTEGER` | `NOT NULL`, `CHECK (gold >= 0)` | `100` | Current gold currency. Non-negative constraint prevents debt. |
| `level` | `INTEGER` | `NOT NULL`, `CHECK (level > 0)` | `1` | Player character level. Must be strictly positive. |
| `xp` | `INTEGER` | `NOT NULL`, `CHECK (xp >= 0)` | `0` | Cumulative experience points. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL` | `NOW()` | Timestamp when the user account was registered. |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL` | `NOW()` | Timestamp of last profile modification. |

---

### 1.2 `npcs`
Stores non-player character definitions, personas, spawn locations, and personality vectors.

| Column Name | Data Type | Constraints | Default | Description |
|---|---|---|---|---|
| `npc_id` | `INTEGER` | `GENERATED ALWAYS AS IDENTITY`, `PRIMARY KEY` | — | Unique surrogate identifier for the NPC. |
| `name` | `VARCHAR(100)` | `NOT NULL`, `UNIQUE` | — | Canonical NPC name. |
| `persona` | `TEXT` | `NOT NULL` | — | Base system prompt establishing character lore and behavioral stance. |
| `location` | `VARCHAR(100)` | `NULLABLE` | — | Virtual coordinate or world zone (e.g., 'Eldoria Market'). |
| `personality_traits` | `JSONB` | `NOT NULL` | `'{}'` | JSON structured traits (e.g., `{"curiosity": 0.8, "patience": 0.3}`). |
| `greeting` | `TEXT` | `NULLABLE` | — | Introductory dialogue uttered on first player engagement. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL` | `NOW()` | Timestamp when NPC record was instantiated. |

---

### 1.3 `items`
Maintains the master catalog of items, equipment, consumables, and quest artifacts available in the world.

| Column Name | Data Type | Constraints | Default | Description |
|---|---|---|---|---|
| `item_id` | `INTEGER` | `GENERATED ALWAYS AS IDENTITY`, `PRIMARY KEY` | — | Unique surrogate identifier for the item. |
| `name` | `VARCHAR(100)` | `NOT NULL`, `UNIQUE` | — | Canonical item name. |
| `description` | `TEXT` | `NULLABLE` | — | Detailed lore and functional description. |
| `base_price` | `INTEGER` | `NOT NULL`, `CHECK (base_price > 0)` | — | Base purchase price in gold units. |
| `item_type` | `VARCHAR(50)` | `NOT NULL`, `CHECK (item_type IN ('weapon', 'armor', 'potion', 'misc', 'quest_item'))` | `'misc'` | Classification category of the item. |
| `rarity` | `VARCHAR(20)` | `NOT NULL`, `CHECK (rarity IN ('common', 'uncommon', 'rare', 'epic', 'legendary'))` | `'common'` | Item scarcity tier. |
| `stock` | `INTEGER` | `NOT NULL` | `-1` | Vendor available stock (`-1` indicates infinite availability). |
| `search_vector` | `TSVECTOR` | `NULLABLE` | — | Precomputed tsvector for full-text lexical search. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL` | `NOW()` | Creation timestamp. |

---

### 1.4 `quests`
Defines available quests, prerequisites, level gates, and reward packages.

| Column Name | Data Type | Constraints | Default | Description |
|---|---|---|---|---|
| `quest_id` | `INTEGER` | `GENERATED ALWAYS AS IDENTITY`, `PRIMARY KEY` | — | Unique surrogate identifier for the quest. |
| `title` | `VARCHAR(150)` | `NOT NULL`, `UNIQUE` | — | Display title for the quest. |
| `description` | `TEXT` | `NOT NULL` | — | Narrative objectives and story context. |
| `reward_gold` | `INTEGER` | `NOT NULL`, `CHECK (reward_gold >= 0)` | `0` | Gold awarded upon verified completion. |
| `reward_xp` | `INTEGER` | `NOT NULL`, `CHECK (reward_xp >= 0)` | `0` | Experience points awarded upon completion. |
| `reward_item_id` | `INTEGER` | `NULLABLE`, `FK -> items(item_id)` | `NULL` | Optional bonus item awarded on completion. |
| `min_level` | `INTEGER` | `NOT NULL`, `CHECK (min_level >= 1)` | `1` | Character level requirement to start quest. |
| `quest_type` | `VARCHAR(50)` | `NOT NULL`, `CHECK (quest_type IN ('main', 'side', 'daily', 'bounty'))` | `'side'` | Quest category classification. |
| `search_vector` | `TSVECTOR` | `NULLABLE` | — | Precomputed tsvector for full-text search. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL` | `NOW()` | Registration timestamp. |

---

### 1.5 `player_inventory`
Associative junction table linking players to the items they currently hold in their bags.

| Column Name | Data Type | Constraints | Default | Description |
|---|---|---|---|---|
| `inventory_id` | `INTEGER` | `GENERATED ALWAYS AS IDENTITY`, `PRIMARY KEY` | — | Unique surrogate inventory slot identifier. |
| `player_id` | `INTEGER` | `NOT NULL`, `FK -> players(player_id)` | — | Referencing player entity. |
| `item_id` | `INTEGER` | `NOT NULL`, `FK -> items(item_id)` | — | Referencing catalog item entity. |
| `quantity` | `INTEGER` | `NOT NULL`, `CHECK (quantity > 0)` | `1` | Stack count. Zero or negative values are disallowed. |
| `acquired_at` | `TIMESTAMPTZ` | `NOT NULL` | `NOW()` | Timestamp when item was first added. |

- **Table-Level Constraints**: `CONSTRAINT uq_player_inventory UNIQUE (player_id, item_id)`

---

### 1.6 `player_quests`
Tracks individual player progress through the quest dependency graph.

| Column Name | Data Type | Constraints | Default | Description |
|---|---|---|---|---|
| `player_quest_id` | `INTEGER` | `GENERATED ALWAYS AS IDENTITY`, `PRIMARY KEY` | — | Unique progression record identifier. |
| `player_id` | `INTEGER` | `NOT NULL`, `FK -> players(player_id)` | — | Referencing player entity. |
| `quest_id` | `INTEGER` | `NOT NULL`, `FK -> quests(quest_id)` | — | Referencing quest entity. |
| `status` | `VARCHAR(20)` | `NOT NULL`, `CHECK (status IN ('not_started', 'in_progress', 'completed', 'failed'))` | `'in_progress'` | Current progression state. |
| `started_at` | `TIMESTAMPTZ` | `NOT NULL` | `NOW()` | Timestamp when quest was initiated. |
| `completed_at` | `TIMESTAMPTZ` | `NULLABLE` | `NULL` | Timestamp when marked completed. |

- **Table-Level Constraints**: `CONSTRAINT uq_player_quest UNIQUE (player_id, quest_id)`

---

### 1.7 `quest_prerequisites`
A self-referencing relationship representing directed edges in the quest prerequisite graph (DAG).

| Column Name | Data Type | Constraints | Default | Description |
|---|---|---|---|---|
| `prerequisite_id` | `INTEGER` | `GENERATED ALWAYS AS IDENTITY`, `PRIMARY KEY` | — | Unique identifier for the prerequisite edge. |
| `quest_id` | `INTEGER` | `NOT NULL`, `FK -> quests(quest_id)` | — | The downstream quest requiring fulfillment. |
| `required_quest_id`| `INTEGER` | `NOT NULL`, `FK -> quests(quest_id)` | — | The mandatory upstream prerequisite quest. |

- **Table-Level Constraints**:
  - `CONSTRAINT uq_quest_prerequisite UNIQUE (quest_id, required_quest_id)`
  - `CONSTRAINT chk_no_self_prerequisite CHECK (quest_id <> required_quest_id)`

---

### 1.8 `inventory_transactions`
Append-only double-entry financial and item movement ledger for security and exploit prevention.

| Column Name | Data Type | Constraints | Default | Description |
|---|---|---|---|---|
| `transaction_id` | `INTEGER` | `GENERATED ALWAYS AS IDENTITY`, `PRIMARY KEY` | — | Unique audit transaction identifier. |
| `player_id` | `INTEGER` | `NOT NULL`, `FK -> players(player_id)` | — | Transacting player entity. |
| `item_id` | `INTEGER` | `NOT NULL`, `FK -> items(item_id)` | — | Transacted catalog item. |
| `transaction_type`| `VARCHAR(20)` | `NOT NULL`, `CHECK (transaction_type IN ('buy', 'sell', 'quest_reward', 'admin_grant'))` | — | Business category of transaction. |
| `quantity` | `INTEGER` | `NOT NULL` | — | Delta quantity (+ for acquisitions, - for sales). |
| `gold_amount` | `INTEGER` | `NOT NULL` | — | Delta gold amount (- for purchases, + for sales). |
| `description` | `VARCHAR(255)` | `NULLABLE` | — | Human-readable explanation. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL` | `NOW()` | Immutable transaction timestamp. |

---

### 1.9 `npc_relationships`
Maintains social sentiment, affinity score, and interaction history between player and NPC pairs.

| Column Name | Data Type | Constraints | Default | Description |
|---|---|---|---|---|
| `relationship_id`| `INTEGER` | `GENERATED ALWAYS AS IDENTITY`, `PRIMARY KEY` | — | Unique surrogate relationship identifier. |
| `player_id` | `INTEGER` | `NOT NULL`, `FK -> players(player_id)` | — | Referencing player entity. |
| `npc_id` | `INTEGER` | `NOT NULL`, `FK -> npcs(npc_id)` | — | Referencing NPC entity. |
| `affinity_score` | `NUMERIC(5,2)` | `NOT NULL`, `CHECK (affinity_score >= -100.00 AND affinity_score <= 100.00)` | `0.00` | Dynamic sentiment score (-100 to +100). |
| `interaction_count`| `INTEGER` | `NOT NULL`, `CHECK (interaction_count >= 0)` | `0` | Total dialogue sessions exchanged. |
| `last_interaction`| `TIMESTAMPTZ` | `NOT NULL` | `NOW()` | Timestamp of most recent conversation. |

- **Table-Level Constraints**: `CONSTRAINT uq_player_npc UNIQUE (player_id, npc_id)`

---

### 1.10 `audit_log`
Autonomous change data capture (CDC) repository populated automatically by PostgreSQL triggers.

| Column Name | Data Type | Constraints | Default | Description |
|---|---|---|---|---|
| `log_id` | `INTEGER` | `GENERATED ALWAYS AS IDENTITY`, `PRIMARY KEY` | — | Unique audit entry identifier. |
| `table_name` | `VARCHAR(50)` | `NOT NULL` | — | Source database table where change occurred. |
| `operation` | `VARCHAR(10)` | `NOT NULL`, `CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE'))` | — | Mutation action. |
| `row_id` | `INTEGER` | `NOT NULL` | — | Primary key value of the mutated record. |
| `old_data` | `JSONB` | `NULLABLE` | — | Snapshot of row values prior to modification. |
| `new_data` | `JSONB` | `NULLABLE` | — | Snapshot of row values after modification. |
| `changed_by` | `VARCHAR(50)` | `NOT NULL` | `CURRENT_USER` | System/DB user executing the mutation. |
| `changed_at` | `TIMESTAMPTZ` | `NOT NULL` | `NOW()` | Exact system timestamp of change event. |

---

## 2. Foreign Key Relationships & Referential Integrity

| Referencing Table | Foreign Key Column | Target Table & Column | ON DELETE Rule | ON UPDATE Rule | Referential Rationale |
|---|---|---|---|---|---|
| `quests` | `reward_item_id` | `items(item_id)` | `SET NULL` | `CASCADE` | Deleting an item catalog row clears the quest bonus item without breaking quest progress. |
| `player_inventory` | `player_id` | `players(player_id)` | `CASCADE` | `CASCADE` | Purging an account removes all inventory stacks owned by that player. |
| `player_inventory` | `item_id` | `items(item_id)` | `RESTRICT` | `CASCADE` | Prevents accidental deletion of items currently held in active player inventories. |
| `player_quests` | `player_id` | `players(player_id)` | `CASCADE` | `CASCADE` | Removing a player automatically drops their quest logs. |
| `player_quests` | `quest_id` | `quests(quest_id)` | `CASCADE` | `CASCADE` | Removing a quest purges in-flight tracking records. |
| `quest_prerequisites` | `quest_id` | `quests(quest_id)` | `CASCADE` | `CASCADE` | If target quest is deleted, its prerequisite requirements are purged. |
| `quest_prerequisites` | `required_quest_id` | `quests(quest_id)` | `RESTRICT` | `CASCADE` | Prevents deletion of a prerequisite quest while downstream quests depend on it. |
| `inventory_transactions` | `player_id` | `players(player_id)` | `CASCADE` | `CASCADE` | Removes audit ledger entries when player account is hard-deleted. |
| `inventory_transactions` | `item_id` | `items(item_id)` | `RESTRICT` | `CASCADE` | Prevents deletion of an item that has historical ledger records. |
| `npc_relationships` | `player_id` | `players(player_id)` | `CASCADE` | `CASCADE` | Cascades social affinity deletion with player removal. |
| `npc_relationships` | `npc_id` | `npcs(npc_id)` | `CASCADE` | `CASCADE` | Cascades social affinity deletion with NPC removal. |

---

## 3. Database Normalization Analysis (Third Normal Form - 3NF)

A relational database schema is in **Third Normal Form (3NF)** if and only if it satisfies First Normal Form (1NF), Second Normal Form (2NF), and exhibits zero transitive functional dependencies for non-prime attributes.

### 3.1 First Normal Form (1NF) Compliance
- **Atomicity**: All column values contain atomic, scalar data types. Multivalued attributes such as items held by players are decomposed into the dedicated junction entity `player_inventory` rather than stored as serialized arrays in `players`. (Note: `personality_traits` uses `JSONB` for unstructured key-value modifiers, but the relational identity and constraints remain completely atomic).
- **Uniqueness**: Every table possesses an explicit primary key defined via `GENERATED ALWAYS AS IDENTITY`.
- **Order Invariance**: Row ordering and column ordering carry no semantic significance.

### 3.2 Second Normal Form (2NF) Compliance
- 2NF requires 1NF compliance and that **no non-prime attribute is partially dependent on any candidate key**.
- In tables with composite candidate keys:
  - `player_inventory`: The candidate key is `(player_id, item_id)`. The non-prime attributes are `quantity` and `acquired_at`. Neither depends solely on `player_id` or `item_id`; the quantity reflects the specific count of *that item* held by *that player*. Thus, full functional dependency exists:
    $$\{ \text{player\_id}, \text{item\_id} \} \to \{ \text{quantity}, \text{acquired\_at} \}$$
  - `player_quests`: Candidate key is `(player_id, quest_id)`. Non-prime attributes are `status`, `started_at`, and `completed_at`. They represent the state of *that quest* for *that player*. Full functional dependency holds.
  - `npc_relationships`: Candidate key is `(player_id, npc_id)`. Non-prime attributes `affinity_score`, `interaction_count`, and `last_interaction` depend entirely on the pair.
- Tables with single-attribute primary keys (`players`, `npcs`, `items`, `quests`, `inventory_transactions`, `audit_log`) are trivially in 2NF because no partial key dependencies can exist.

### 3.3 Third Normal Form (3NF) Compliance
- 3NF requires 2NF compliance and that **no transitive dependencies exist** ($X \to Y \to Z$ where $Z$ is a non-prime attribute and $Y$ is not a candidate key).
- In our schema:
  - In `player_inventory`, we do **not** store `item_name`, `base_price`, or `item_type`. Including `base_price` would create a transitive dependency:
    $$\text{inventory\_id} \to \text{item\_id} \to \text{base\_price}$$
    Instead, prices and descriptions are strictly isolated in `items`, satisfying 3NF.
  - In `quests`, we store `reward_item_id` referencing `items.item_id`, rather than replicating item attributes in `quests`.
  - In `npc_relationships`, we store affinity metrics without replicating NPC lore (`persona`, `location`), eliminating redundant dependencies.
  - In `inventory_transactions`, each ledger row stores the historical snapshot of transaction values (`gold_amount`, `quantity`) while referencing the master entities `player_id` and `item_id`.

**Conclusion**: The relational schema strictly adheres to 3NF, eliminating update, insertion, and deletion anomalies while maintaining maximum storage efficiency and referential integrity.

---

## 4. Qdrant Vector Collection Specification

To enable contextual memory retrieval for generative NPC dialogues without polluting the relational transaction engine, dialogue embeddings are managed in **Qdrant**.

### 4.1 Collection Parameters
- **Collection Name**: `npc_memories`
- **Vector Dimension**: `384` (Derived from the `sentence-transformers/all-MiniLM-L6-v2` dense embedding model)
- **Distance Metric**: `Cosine` ($1.0 - \frac{u \cdot v}{\|u\|_2 \|v\|_2}$)
- **HNSW Parameters**:
  - `m`: `16` (Number of bidirectional links per node)
  - `ef_construct`: `100` (Search depth during construction)
  - `on_disk`: `false` (Kept in memory for sub-millisecond retrieval latency)

### 4.2 Payload Schema & Indexing

Each vector point represents an atomic dialogue exchange or contextual memory snippet associated with a player and NPC.

| Payload Field | Data Type | Qdrant Index Type | Nullable | Description |
|---|---|---|---|---|
| `player_id` | `integer` | `integer` (Index) | No | PostgreSQL `players.player_id` foreign reference for strict multi-tenant filtering. |
| `npc_id` | `integer` | `integer` (Index) | No | PostgreSQL `npcs.npc_id` foreign reference isolating memory by character. |
| `session_id` | `string` | `keyword` (Index) | No | UUID tracking the specific continuous dialogue session. |
| `text` | `string` | Full-text (Optional) | No | Raw textual utterance or distilled memory observation. |
| `role` | `string` | `keyword` (Index) | No | Speaker entity: `'player'` or `'npc'`. |
| `importance` | `float` | `float` (Index) | No | Cognitive significance weight assigned to memory ($0.0$ to $1.0$). |
| `timestamp` | `float` | `float` (Index) | No | Unix epoch timestamp for recency-decay scoring. |
| `emotion` | `string` | `keyword` (Index) | Yes | Detected emotional valence (e.g., `'neutral'`, `'friendly'`, `'hostile'`, `'curious'`). |

### 4.3 Payload Filtering & Similarity Formulation
During chat fusion, memory retrieval combines payload filters with cosine vector search:
```json
{
  "filter": {
    "must": [
      { "key": "player_id", "match": { "value": 1 } },
      { "key": "npc_id", "match": { "value": 2 } }
    ]
  },
  "limit": 5,
  "with_payload": true
}
```
This guarantees that memories belonging to another player or an unrelated NPC can never leak into the dialogue prompt context.
