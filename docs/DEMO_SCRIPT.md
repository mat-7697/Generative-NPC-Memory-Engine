# Live Demonstration Script (8 – 10 Minutes)

This script outlines the exact sequence for presenting the **Generative NPC Memory Engine** to evaluators. It is calibrated for an 8 to 10 minute presentation following the course grading rubric.

---

## Timing Overview

| Segment | Topic | Target Duration | Cum. Time |
|---|---|---|---|
| 1 | Architecture Overview | 30s | 0:30 |
| 2 | ER Diagram & Relational Schema (3NF) | 60s | 1:30 |
| 3 | PostgreSQL DDL, Constraints & Indexes | 60s | 2:30 |
| 4 | Qdrant Vector Collection & Indexing | 30s | 3:00 |
| 5 | Authentication: Register & Login (JWT) | 60s | 4:00 |
| 6 | ACID Transactions: Shop & Inventory Stored Proc | 60s | 5:00 |
| 7 | Generative Chat & Context Fusion Flow | 90s | 6:30 |
| 8 | Recursive CTE: Quest Prerequisite Dependency Tree | 60s | 7:30 |
| 9 | Admin Dashboard: Audit Log CDC & Leaderboard | 60s | 8:30 |
| 10 | Automated Test Suite (Constraints, Concurrency) | 30s | 9:00 |
| 11 | RBAC & Row-Level Security (RLS) Verification | 30s | 9:30 |

---

## Detailed Step-by-Step Presentation Script

### Step 1: System Architecture Overview (0:00 – 0:30)
- **Visual**: Display `docs/ARCHITECTURE.md` Mermaid diagram or browser UI.
- **Presenter Dialogue**:
  > *"Good morning evaluators. Today we present the Generative NPC Memory Engine. Our system bridges two specialized database paradigms: PostgreSQL 16 handles structured game economics and ACID transactions, while Qdrant serves as our cognitive vector database storing 384-dimensional conversational memories. FastAPI coordinates the chat context fusion, and Next.js 14 provides the player and administrator interface."*

---

### Step 2: ER Diagram & 3NF Schema (0:30 – 1:30)
- **Visual**: Open `docs/ER_DIAGRAM.md` and show the Mermaid diagram.
- **Presenter Dialogue**:
  > *"Here is our Entity-Relationship model consisting of 10 tables. Notice our core junction entities: `player_inventory` resolving players to items with unique stack constraints, `player_quests` tracking progress states, and `quest_prerequisites`, a self-referencing directed graph on quests. The schema is strictly in Third Normal Form (3NF): all attributes depend on the key, the whole key, and nothing but the key, eliminating update anomalies while isolating prices in `items`."*

---

### Step 3: PostgreSQL Tables, Constraints & Indexes (1:30 – 2:30)
- **Visual**: Open terminal / pgAdmin running psql:
  ```bash
  psql -U postgres -d npc_memory_engine -c "\dt"
  psql -U postgres -d npc_memory_engine -c "\d players"
  psql -U postgres -d npc_memory_engine -c "\d player_inventory"
  ```
- **Presenter Dialogue**:
  > *"In PostgreSQL, all 10 tables are protected by database-level constraints. Notice `CHECK (gold >= 0)` on players, `CHECK (quantity > 0)` on inventory, and `UNIQUE(player_id, item_id)`. We have also created B-tree indexes on foreign keys and GIN indexes on tsvector columns for full-text search across items and quests."*

---

### Step 4: Qdrant Vector Collection & Payloads (2:30 – 3:00)
- **Visual**: Open Qdrant Web UI at `http://localhost:6333/dashboard` or run:
  ```bash
  curl http://localhost:6333/collections/npc_memories
  ```
- **Presenter Dialogue**:
  > *"In Qdrant, we have the `npc_memories` collection configured with 384-dimensional dense vectors using Cosine distance, generated via sentence-transformers. Notice our payload indexes on `player_id`, `npc_id`, `timestamp`, and `importance`. This allows Qdrant to filter by player and NPC directly during HNSW graph exploration."*

---

### Step 5: User Registration & Login (3:00 – 4:00)
- **Visual**: Switch to Next.js Frontend (`http://localhost:3000/register`).
- **Action**:
  1. Register a new user: `adventurer1`, password `SecretPassword123!`.
  2. Log in. Inspect Network tab to show JWT Bearer token containing `player_id` and role `player`.
- **Presenter Dialogue**:
  > *"When we register, passwords are never stored in plaintext—they are hashed using Bcrypt with 12 salt rounds. Upon login, FastAPI returns an HMAC-SHA256 JWT containing player claims, which are passed to subsequent requests to enforce Row-Level Security."*

---

### Step 6: Shop & Stored Procedure Execution (4:00 – 5:00)
- **Visual**: Navigate to `/shop`.
- **Action**:
  1. Point out starting balance: 100 Gold.
  2. Click **Buy** on a *Health Potion* (Price: 25 Gold).
  3. Show balance dynamically decrement to 75 Gold, and inventory quantity increase to 1.
  4. Query PostgreSQL in terminal to prove ACID procedure execution:
     ```sql
     SELECT * FROM inventory_transactions WHERE player_id = 1 ORDER BY created_at DESC LIMIT 1;
     SELECT * FROM audit_log ORDER BY changed_at DESC LIMIT 1;
     ```
- **Presenter Dialogue**:
  > *"Purchasing an item does not run simple client updates. It invokes our `buy_item` stored procedure, which locks the player's row using `SELECT ... FOR UPDATE`, checks balance and stock, deducts gold, increments inventory, and records an immutable audit ledger entry in `inventory_transactions`. Our database trigger also recorded a CDC entry in `audit_log`."*

---

### Step 7: Generative Chat & Context Fusion Pipeline (5:00 – 6:30)
- **Visual**: Navigate to `/chat` and select NPC *Elric the Blacksmith*.
- **Action**:
  1. Send message: *"Do you have any recommendations for a beginner adventurer?"*
  2. Show NPC reply mentioning the player's current level and inventory.
  3. Send follow-up: *"Remember that I want to explore the Whispering Ruins tomorrow."*
  4. Show Qdrant memory inspector updating with the new vector point.
  5. Ask: *"What place did I say I wanted to visit?"*
  6. Show NPC replying: *"You mentioned earlier that you intended to explore the Whispering Ruins tomorrow."*
- **Presenter Dialogue**:
  > *"This is our Context Fusion Pipeline. When the player speaks, FastAPI loads relational game state from PostgreSQL (gold, level, items, affinity) and queries Qdrant for top-K semantically relevant past memories filtered by `player_id` and `npc_id`. Both are injected into the system prompt. Even across separate sessions, Elric remembers past statements through Qdrant, while accurately knowing the player's wallet balance from PostgreSQL."*

---

### Step 8: Quest System & Recursive CTE Prerequisite Tree (6:30 – 7:30)
- **Visual**: Navigate to `/quests`.
- **Action**:
  1. Show Quest list: Quest 1 (*Rats in the Cellar* - no prerequisites) is unlocked.
  2. Quest 3 (*Dragon's Lair*) is locked because it depends on Quest 2, which depends on Quest 1.
  3. Attempt to start Quest 3: UI blocks it.
  4. Execute the recursive CTE query in psql:
     ```sql
     SELECT * FROM can_start_quest(1, 3); -- Returns FALSE
     ```
- **Presenter Dialogue**:
  > *"Our quest prerequisite system is modeled as a Directed Acyclic Graph (DAG) in `quest_prerequisites`. To evaluate whether a player can accept a quest, our `can_start_quest` procedure executes a `WITH RECURSIVE` CTE that traverses all parent and ancestor requirements and verifies completion against `player_quests`."*

---

### Step 9: Admin Panel, Audit Log & Analytical Views (7:30 – 8:30)
- **Visual**: Log out and log in as `admin`. Navigate to `/admin`.
- **Action**:
  1. View `player_leaderboard` view (ranks players by level, XP, and inventory net worth).
  2. View `npc_popularity` view (dialogue turns and average sentiment affinity).
  3. Inspect `audit_log` showing every change captured across the database.
- **Presenter Dialogue**:
  > *"The admin dashboard provides global oversight powered by advanced analytical SQL views using window ranking functions (`DENSE_RANK()`) and multi-table aggregations. The audit log reflects trigger-based Change Data Capture (CDC) with JSONB before-and-after snapshots."*

---

### Step 10: Automated Test Suite (8:30 – 9:00)
- **Visual**: In terminal, run pytest:
  ```bash
  pytest backend/tests/ -v
  ```
- **Presenter Dialogue**:
  > *"We have an extensive test suite verifying check constraint enforcement, procedure rollbacks on insufficient funds, recursive CTE accuracy, and concurrent transaction race conditions with multiple simulated parallel buyers."*

---

### Step 11: RBAC & Row-Level Security (RLS) Proof (9:00 – 9:30)
- **Visual**: Open terminal and run demonstration query:
  ```sql
  SET ROLE app_player;
  SET LOCAL app.current_player_id = '1';
  SELECT * FROM player_inventory; -- Shows only Player 1's items
  SET LOCAL app.current_player_id = '2';
  SELECT * FROM player_inventory; -- Shows only Player 2's items
  RESET ROLE;
  ```
- **Presenter Dialogue**:
  > *"Finally, we demonstrate PostgreSQL Row-Level Security. Notice how switching `app.current_player_id` dynamically isolates inventory rows at the database engine level. This guarantees complete multi-tenant security independent of application logic. Thank you, and we welcome your questions!"*
