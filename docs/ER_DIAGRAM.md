# Entity-Relationship (ER) Diagram

This document presents the complete Entity-Relationship model for the **Generative NPC Memory Engine** database. The relational database schema is implemented in PostgreSQL 16+ and comprises 10 core tables designed in Third Normal Form (3NF), supporting ACID-compliant transactional gameplay, quest dependency graphs, audit trails, and multi-tenant player isolation.

---

## 1. Complete Mermaid ER Diagram

```mermaid
erDiagram
    PLAYERS ||--o{ PLAYER_INVENTORY : "holds"
    ITEMS ||--o{ PLAYER_INVENTORY : "stocked_in"
    PLAYERS ||--o{ PLAYER_QUESTS : "undertakes"
    QUESTS ||--o{ PLAYER_QUESTS : "tracked_in"
    QUESTS ||--o{ QUEST_PREREQUISITES : "has_prerequisite"
    QUESTS ||--o{ QUEST_PREREQUISITES : "is_prerequisite_for"
    PLAYERS ||--o{ INVENTORY_TRANSACTIONS : "executes"
    ITEMS ||--o{ INVENTORY_TRANSACTIONS : "transacted_in"
    PLAYERS ||--o{ NPC_RELATIONSHIPS : "develops_affinity"
    NPCS ||--o{ NPC_RELATIONSHIPS : "maintains_bond"
    ITEMS ||--o| QUESTS : "rewards_as_item"

    PLAYERS {
        int player_id PK "Identity auto-increment"
        string username "Unique username"
        string email "Unique email address"
        string password_hash "Bcrypt hash"
        string role "player | admin"
        int gold "Available currency >= 0"
        int level "Player level >= 1"
        int xp "Experience points >= 0"
        timestamptz created_at "Account registration"
        timestamptz updated_at "Profile timestamp"
    }

    NPCS {
        int npc_id PK "Identity auto-increment"
        string name "Unique character name"
        text persona "System prompt persona"
        string location "World location / zone"
        jsonb personality_traits "Traits key-values"
        text greeting "Initial dialogue greeting"
        timestamptz created_at "Spawn creation time"
    }

    ITEMS {
        int item_id PK "Identity auto-increment"
        string name "Unique item name"
        text description "Lore and stats"
        int base_price "Shop cost > 0"
        string item_type "weapon | armor | potion | misc | quest_item"
        string rarity "common | uncommon | rare | epic | legendary"
        int stock "Available vendor inventory (-1 unlimited)"
        tsvector search_vector "Full-text search index"
        timestamptz created_at "Item creation time"
    }

    QUESTS {
        int quest_id PK "Identity auto-increment"
        string title "Quest display title"
        text description "Objectives and lore"
        int reward_gold "Gold reward >= 0"
        int reward_xp "XP reward >= 0"
        int reward_item_id FK "Nullable FK -> items.item_id"
        int min_level "Level prerequisite >= 1"
        string quest_type "main | side | daily | bounty"
        tsvector search_vector "Full-text search index"
        timestamptz created_at "Quest registration"
    }

    PLAYER_INVENTORY {
        int inventory_id PK "Identity auto-increment"
        int player_id FK "FK -> players.player_id"
        int item_id FK "FK -> items.item_id"
        int quantity "Item count > 0"
        timestamptz acquired_at "First acquisition time"
    }

    PLAYER_QUESTS {
        int player_quest_id PK "Identity auto-increment"
        int player_id FK "FK -> players.player_id"
        int quest_id FK "FK -> quests.quest_id"
        string status "not_started | in_progress | completed | failed"
        timestamptz started_at "Quest start timestamp"
        timestamptz completed_at "Completion timestamp"
    }

    QUEST_PREREQUISITES {
        int prerequisite_id PK "Identity auto-increment"
        int quest_id FK "Target quest FK -> quests.quest_id"
        int required_quest_id FK "Prerequisite quest FK -> quests.quest_id"
    }

    INVENTORY_TRANSACTIONS {
        int transaction_id PK "Identity auto-increment"
        int player_id FK "FK -> players.player_id"
        int item_id FK "FK -> items.item_id"
        string transaction_type "buy | sell | quest_reward | admin_grant"
        int quantity "Signed quantity delta"
        int gold_amount "Signed gold delta"
        string description "Contextual audit notes"
        timestamptz created_at "Transaction timestamp"
    }

    NPC_RELATIONSHIPS {
        int relationship_id PK "Identity auto-increment"
        int player_id FK "FK -> players.player_id"
        int npc_id FK "FK -> npcs.npc_id"
        numeric affinity_score "Sentiment score (-100.0 to 100.0)"
        int interaction_count "Dialogue exchange count"
        timestamptz last_interaction "Most recent dialogue time"
    }

    AUDIT_LOG {
        int log_id PK "Identity auto-increment"
        string table_name "Target modified table"
        string operation "INSERT | UPDATE | DELETE"
        int row_id "Primary key of target row"
        jsonb old_data "Row state before change"
        jsonb new_data "Row state after change"
        string changed_by "Database user or application role"
        timestamptz changed_at "Timestamp of audit event"
    }
```

---

## 2. Entity Descriptions & Primary Keys

| # | Entity Name | Primary Key | Description & Domain Role |
|---|---|---|---|
| 1 | `players` | `player_id` | Core user identity, credentials, progression (level/XP), and liquid currency (gold). Protected by strict non-negative check constraints. |
| 2 | `npcs` | `npc_id` | Non-player characters with distinctive personas, personality traits stored in JSONB, world locations, and dialogue prompts. |
| 3 | `items` | `item_id` | Master catalog of gear, consumables, and quest items, including base prices, rarity tiers, and GIN-indexed tsvectors for full-text search. |
| 4 | `quests` | `quest_id` | Objectives and missions offering XP, gold, and optional item rewards (`reward_item_id`). Supports full-text search. |
| 5 | `player_inventory` | `inventory_id` | Junction table associating players with items. Enforces `UNIQUE(player_id, item_id)` and `quantity > 0`. |
| 6 | `player_quests` | `player_quest_id` | State tracking for quest progression (`in_progress`, `completed`, `failed`), enforcing `UNIQUE(player_id, quest_id)`. |
| 7 | `quest_prerequisites` | `prerequisite_id` | Self-referential Directed Acyclic Graph (DAG) over `quests` defining completion prerequisites, traversed via recursive CTEs. |
| 8 | `inventory_transactions`| `transaction_id` | Immutable double-entry financial and item movement ledger tracking purchases, sales, and rewards. |
| 9 | `npc_relationships` | `relationship_id` | Dynamic player-NPC social dynamics, tracking emotional affinity (`-100.0` to `+100.0`) and total interactions. |
| 10 | `audit_log` | `log_id` | Autonomous change data capture (CDC) repository populated by PostgreSQL triggers recording before-and-after JSONB diffs. |

---

## 3. Relationships & Cardinalities Detailed

1. **`players` to `player_inventory` (1 : 0..*)**
   - **Cardinality**: One player can hold zero, one, or many inventory items (`1--o{`).
   - **Foreign Key**: `player_inventory.player_id` references `players.player_id` with `ON DELETE CASCADE`.
   - **Integrity**: Enforced by composite uniqueness `UNIQUE (player_id, item_id)`.

2. **`items` to `player_inventory` (1 : 0..*)**
   - **Cardinality**: One catalog item can be possessed by zero or multiple players (`1--o{`).
   - **Foreign Key**: `player_inventory.item_id` references `items.item_id` with `ON DELETE RESTRICT` (items cannot be dropped if held).

3. **`players` to `player_quests` (1 : 0..*)**
   - **Cardinality**: One player may accept zero or multiple quests (`1--o{`).
   - **Foreign Key**: `player_quests.player_id` references `players.player_id` with `ON DELETE CASCADE`.
   - **Integrity**: Enforced by composite uniqueness `UNIQUE (player_id, quest_id)`.

4. **`quests` to `player_quests` (1 : 0..*)**
   - **Cardinality**: One quest may be undertaken by zero or multiple players (`1--o{`).
   - **Foreign Key**: `player_quests.quest_id` references `quests.quest_id` with `ON DELETE CASCADE`.

5. **`quests` to `quest_prerequisites` [Target Quest] (1 : 0..*)**
   - **Cardinality**: One quest can have zero or multiple prerequisite quests (`1--o{`).
   - **Foreign Key**: `quest_prerequisites.quest_id` references `quests.quest_id` with `ON DELETE CASCADE`.

6. **`quests` to `quest_prerequisites` [Required Quest] (1 : 0..*)**
   - **Cardinality**: One quest can act as a prerequisite for zero or multiple other quests (`1--o{`).
   - **Foreign Key**: `quest_prerequisites.required_quest_id` references `quests.quest_id` with `ON DELETE RESTRICT`.

7. **`players` to `inventory_transactions` (1 : 0..*)**
   - **Cardinality**: One player can have zero or multiple transaction records (`1--o{`).
   - **Foreign Key**: `inventory_transactions.player_id` references `players.player_id` with `ON DELETE CASCADE`.

8. **`items` to `inventory_transactions` (1 : 0..*)**
   - **Cardinality**: One item can appear in zero or multiple transaction entries (`1--o{`).
   - **Foreign Key**: `inventory_transactions.item_id` references `items.item_id` with `ON DELETE RESTRICT`.

9. **`players` to `npc_relationships` (1 : 0..*)**
   - **Cardinality**: One player can interact with zero or multiple distinct NPCs (`1--o{`).
   - **Foreign Key**: `npc_relationships.player_id` references `players.player_id` with `ON DELETE CASCADE`.
   - **Integrity**: Enforced by `UNIQUE (player_id, npc_id)`.

10. **`npcs` to `npc_relationships` (1 : 0..*)**
    - **Cardinality**: One NPC maintains social relationships with zero or many players (`1--o{`).
    - **Foreign Key**: `npc_relationships.npc_id` references `npcs.npc_id` with `ON DELETE CASCADE`.

11. **`items` to `quests` [Reward Item] (1 : 0..1)**
    - **Cardinality**: An item can optionally be assigned as a reward for quests; a quest rewards zero or one item (`1--o|`).
    - **Foreign Key**: `quests.reward_item_id` references `items.item_id` with `ON DELETE SET NULL`.

12. **`audit_log` (Autonomous)**
    - **Design**: Does not maintain hard foreign key constraints to prevent audit record loss if entities are expunged, recording `table_name` and `row_id` alongside full JSONB state payloads (`old_data`, `new_data`).

---

## 4. Vector Memory Integration (Qdrant)

While PostgreSQL manages the relational game state above, high-dimensional conversation memory is stored in **Qdrant**:
- **Collection**: `npc_memories`
- **Vector Space**: 384-dimensional dense vectors (`sentence-transformers/all-MiniLM-L6-v2`) with Cosine Distance.
- **Relational Linkage**: Every vector payload stores `player_id` and `npc_id` matching `players.player_id` and `npcs.npc_id`.
- **Payload Indexing**: Filtered search queries combine exact relational IDs (`player_id = X AND npc_id = Y`) with semantic nearest-neighbor memory retrieval.
