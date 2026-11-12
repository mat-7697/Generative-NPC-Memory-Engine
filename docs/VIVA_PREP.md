# Comprehensive Viva Voce Preparation Guide

This viva preparation guide covers the **Generative NPC Memory Engine** project, organized by all **14 rubric evaluation items**. It includes direct answers to anticipated examiner questions, technical deep dives, and "How would you modify X" scenario questions.

---

## Part 1: Questions Organized by Rubric Item (Items 1 – 14)

### Rubric Item 1: Entity-Relationship Diagram (2 Marks)
**Q1: How many entities are in your ER model, and what are the main junction relationships?**
> **Answer**: There are 10 entities in total. The primary junction tables are `player_inventory` (resolving the $M:N$ relationship between `players` and `items`), `player_quests` (resolving the $M:N$ relationship between `players` and `quests`), `npc_relationships` (resolving the $M:N$ relationship between `players` and `npcs`), and `quest_prerequisites` (a self-referencing relationship resolving the directed graph of prerequisites on `quests`).

**Q2: What is the cardinality between `quests` and `items` for rewards?**
> **Answer**: It is a $1:0..1$ relationship. A quest can optionally reward at most one catalog item (`reward_item_id` foreign key referencing `items.item_id`), while an item can be configured as a reward for zero, one, or multiple quests.

---

### Rubric Item 2: Relational Schema & Normalization (3 Marks)
**Q1: Prove that your schema is in Third Normal Form (3NF).**
> **Answer**: 
> 1. **1NF**: Every table has a declared primary key (`GENERATED ALWAYS AS IDENTITY`), all attributes contain atomic scalar values, and multivalued attributes (like inventory stacks) are factored into dedicated tables.
> 2. **2NF**: It satisfies 1NF, and in tables with composite candidate keys (`player_inventory`, `player_quests`, `npc_relationships`), all non-prime attributes functionally depend on the entire candidate key, not a proper subset. For example, `player_inventory.quantity` depends on the combination of `(player_id, item_id)`.
> 3. **3NF**: It satisfies 2NF, and there are no transitive dependencies ($X \to Y \to Z$ where $Z$ is non-prime and $Y$ is not a superkey). For instance, `player_inventory` does not store `item_name` or `base_price`; those belong strictly in `items`.

**Q2: Why did you choose surrogate keys (`IDENTITY`) instead of composite primary keys in junction tables?**
> **Answer**: We use surrogate integer primary keys (`inventory_id`, `player_quest_id`) for simplified foreign referencing, ORM indexing efficiency, and uniform API routing, while strictly enforcing business candidate key uniqueness via explicit `UNIQUE (player_id, item_id)` table constraints.

---

### Rubric Item 3: SQL DDL, Constraints & Indexes (4 Marks)
**Q1: What database-level constraints prevent game balance exploits?**
> **Answer**: We enforce check constraints at the PostgreSQL kernel level:
> - `CHECK (gold >= 0)` on `players` prevents negative gold debt or underflow bugs.
> - `CHECK (quantity > 0)` on `player_inventory` blocks zero or negative inventory stacks.
> - `CHECK (base_price > 0)` on `items` guarantees positive pricing.
> - `CHECK (affinity_score >= -100.00 AND affinity_score <= 100.00)` on `npc_relationships` confines sentiment boundaries.

**Q2: What index types did you use and why?**
> **Answer**: 
> - **B-Tree indexes**: Used for primary keys, foreign keys, and unique columns (`username`, `email`, `(player_id, item_id)`) providing $\mathcal{O}(\log N)$ lookups and fast join processing.
> - **GIN (Generalized Inverted Index)**: Configured on `tsvector` columns in `items` and `quests` to accelerate lexical full-text search (`to_tsquery()`).

---

### Rubric Item 4: Qdrant Vector Collection (4 Marks)
**Q1: How is the Qdrant collection configured?**
> **Answer**: The collection `npc_memories` uses 384-dimensional dense vectors with `Cosine` distance, matching the dimensionality of the `sentence-transformers/all-MiniLM-L6-v2` model. The index uses HNSW graph parameters ($M=16, \text{ef\_construct}=100$).

**Q2: Which payload fields are indexed in Qdrant and why?**
> **Answer**: `player_id` (integer) and `npc_id` (integer) are indexed to enable fast payload filtering during HNSW graph exploration. This ensures that nearest-neighbor vector search only scans memories belonging to the transacting player and NPC. `timestamp` and `importance` are indexed as float types to support temporal decay and importance weighting.

---

### Rubric Item 5: Technology Justification (1 Mark)
**Q1: Why couldn't you use just PostgreSQL or just Qdrant?**
> **Answer**: PostgreSQL is an ACID-compliant relational database engineered for multi-table transactions, row-level locking, foreign key integrity, and relational algebra. It cannot efficiently execute nearest-neighbor searches over hundreds of thousands of high-dimensional vectors under high concurrency without starving transactional buffer pools. Conversely, Qdrant is an approximate vector search engine; it does not support ACID multi-table transactions, foreign key cascades, or declarative constraints (`CHECK (gold >= 0)`). A polyglot persistence architecture leverages the specialized strengths of each engine.

---

### Rubric Item 6: Data Manipulation Language (DML) (4 Marks)
**Q1: How do you handle item stack additions versus updates in DML?**
> **Answer**: We use PostgreSQL's `INSERT ... ON CONFLICT (player_id, item_id) DO UPDATE SET quantity = player_inventory.quantity + EXCLUDED.quantity`, which atomically increments existing item stacks or creates new inventory rows without race conditions.

---

### Rubric Item 7: Advanced Queries (4 Marks)
**Q1: Name the complex SQL queries implemented in the system.**
> **Answer**: 
> 1. **Multi-table JOINs**: Joining `players`, `player_inventory`, and `items` to compute inventory net worth.
> 2. **GROUP BY with HAVING**: Finding high-tier merchants with average item price $> 100$ gold.
> 3. **Correlated Subqueries**: Identifying players whose gold balance exceeds the average gold balance of players at their same character level.
> 4. **Window Functions**: `DENSE_RANK() OVER (ORDER BY level DESC, xp DESC)` for dynamic player leaderboards.
> 5. **Recursive CTE**: `WITH RECURSIVE quest_tree AS (...)` to traverse arbitrary quest prerequisite dependency graphs.

---

### Rubric Item 8: Stored Procedures, Triggers & Recursive CTE (6 Marks)
**Q1: Explain how the `buy_item` stored procedure prevents race conditions.**
> **Answer**: `buy_item(p_player_id, p_item_id, p_quantity)` runs inside an explicit transaction block. It performs a pessimistic row lock via `SELECT gold FROM players WHERE player_id = p_player_id FOR UPDATE` and checks item stock. If the player has insufficient gold or the item is out of stock, it raises an exception, triggering an automatic rollback. Otherwise, it deducts gold, updates/inserts inventory, decrements stock, and inserts an immutable audit row into `inventory_transactions`.

**Q2: Explain the audit trigger on `player_inventory`.**
> **Answer**: An `AFTER INSERT OR UPDATE OR DELETE` trigger on `player_inventory` executes an audit function that captures the operation type, target row ID, `to_jsonb(OLD)` (if update/delete), and `to_jsonb(NEW)` (if insert/update), inserting a permanent change record into `audit_log`.

**Q3: How does the recursive CTE check if a quest can be started?**
> **Answer**: The recursive CTE defines:
> - **Anchor Member**: Selects direct prerequisites from `quest_prerequisites` for target `quest_id`.
> - **Recursive Member**: Joins `quest_prerequisites` on `qp.quest_id = qt.required_quest_id` to walk up the prerequisite tree to root ancestors.
> - **Verification**: Performs an `EXCEPT` or `NOT IN` comparison against the player's completed quests in `player_quests WHERE status = 'completed'`. If any prerequisite is missing, `can_start_quest` returns `FALSE`.

---

### Rubric Item 9: Qdrant CRUD & Features (7 Marks)
**Q1: What operations are exposed for Qdrant memories?**
> **Answer**: We expose complete CRUD via API and UI:
> - **Create**: Vector point upsert with embeddings and metadata payload.
> - **Read / Search**: Nearest-neighbor cosine search with payload filters (`player_id`, `npc_id`).
> - **Update**: Modifying memory text, recomputing embedding, or updating importance score.
> - **Delete**: Purging specific memory points by UUID or clearing all memories for a player-NPC pair.

---

### Rubric Item 10: Next.js Frontend (3 Marks)
**Q1: What is the structure of your Next.js application?**
> **Answer**: Built using Next.js 14 App Router with TypeScript and Tailwind CSS. It features distinct pages:
> - `/login` & `/register`: JWT authentication
> - `/dashboard`: Player stats, leaderboards, net worth
> - `/chat`: Interactive dialogue with NPCs showing real-time memory retrieval
> - `/shop`: Merchant browsing and item purchasing via stored procedures
> - `/quests`: Quest dependency tree visualization and status tracking
> - `/memories`: Qdrant memory inspector (CRUD)
> - `/admin`: Audit log review and NPC management

---

### Rubric Item 11: Backend / API Integration (2 Marks)
**Q1: How does FastAPI connect to PostgreSQL?**
> **Answer**: FastAPI utilizes an asynchronous connection pool via `asyncpg` configured in `database.py`. Using a connection pool avoids the overhead of opening TCP connections on every HTTP request, supporting high concurrency while enforcing transaction boundaries.

---

### Rubric Item 12: Authentication & RBAC (4 Marks)
**Q1: How is authorization enforced at both the API and database levels?**
> **Answer**: 
> 1. **API Level**: FastAPI dependencies decode the JWT bearer token, inspect the `role` claim (`'player'` vs `'admin'`), and guard sensitive routes (`/admin/*`).
> 2. **Database Level**: PostgreSQL roles `app_admin` and `app_player` have restricted `GRANT` privileges. Furthermore, **Row-Level Security (RLS)** is enabled on `player_inventory` and `player_quests`, ensuring a player can only access rows matching `app.current_player_id`.

---

### Rubric Item 13: Documentation & Repository (2 Marks)
**Q1: What documentation artifacts are provided?**
> **Answer**: Complete ER diagram (`docs/ER_DIAGRAM.md`), Relational Schema (`docs/SCHEMA.md`), Technical Justification (`docs/TECH_JUSTIFICATION.md`), Data Dictionary (`docs/DATA_DICTIONARY.md`), Architecture (`docs/ARCHITECTURE.md`), Contributions (`CONTRIBUTIONS.md`), and Viva Prep (`VIVA_PREP.md`).

---

### Rubric Item 14: Originality & Project Contribution (4 Marks)
**Q1: What makes this project original beyond standard CRUD?**
> **Answer**: The system pioneers a **Chat Context Fusion Pipeline**: it retrieves past conversational memories from Qdrant and relational player state from PostgreSQL (gold, level, items, affinity), dynamically injecting both into an LLM system prompt. The NPC's dialogue adapts in real-time based on whether the player is wealthy, completed certain quests, or has a hostile or friendly affinity.

---

## Part 2: Technical Deep Dives

### Deep Dive 1: ACID Guarantees in `buy_item` Stored Procedure
- **Atomicity**: `BEGIN ... COMMIT / ROLLBACK` ensures that gold deduction, item increment, and audit logging either all succeed or none take effect.
- **Consistency**: Invariants like `CHECK (gold >= 0)` and `CHECK (quantity > 0)` are verified before commit.
- **Isolation**: `SELECT gold FROM players WHERE player_id = p_player_id FOR UPDATE` locks the player row. If two concurrent API calls attempt to spend 80 gold when the player only has 100 gold, the second transaction is queued; once the first completes and deducts 80 gold, the second transaction reads the updated balance (20 gold), fails the balance check, and rolls back cleanly without double-spending.
- **Durability**: Committed transactions are flushed to the Write-Ahead Log (WAL).

### Deep Dive 2: Recursive CTE Prerequisite Traversal
```sql
WITH RECURSIVE PrereqTree AS (
    -- Anchor Member: Direct prerequisites for quest 10
    SELECT quest_id, required_quest_id, 1 AS depth
    FROM quest_prerequisites
    WHERE quest_id = 10
    
    UNION ALL
    
    -- Recursive Member: Prerequisites of the prerequisites
    SELECT qp.quest_id, qp.required_quest_id, pt.depth + 1
    FROM quest_prerequisites qp
    INNER JOIN PrereqTree pt ON qp.quest_id = pt.required_quest_id
)
SELECT DISTINCT required_quest_id FROM PrereqTree;
```
This query traverses arbitrary graph depths (parent, grandparent, etc.) without requiring fixed self-joins or client-side iteration.

### Deep Dive 3: Dense Vector Embeddings & Cosine Similarity
- The `sentence-transformers/all-MiniLM-L6-v2` neural network maps text into a 384-dimensional hypersphere where semantic similarity corresponds to geometric proximity.
- Cosine similarity measures the angle between normalized vectors $\mathbf{u}$ and $\mathbf{v}$:
  $$\text{Cosine Similarity}(\mathbf{u}, \mathbf{v}) = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\|_2 \|\mathbf{v}\|_2}$$
- Values range from `-1.0` (opposite) to `+1.0` (identical). Qdrant indexes these vectors in an HNSW graph for sub-millisecond approximate nearest neighbor lookups.

---

## Part 3: "How Would You Modify X?" Viva Practice

### Question 1: "How would you add an item durability or weapon degradation system?"
> **Answer**: 
> 1. Alter `player_inventory` by adding a column: `ALTER TABLE player_inventory ADD COLUMN current_durability INTEGER NOT NULL DEFAULT 100 CHECK (current_durability >= 0);`
> 2. Alter `items` by adding `max_durability INTEGER NOT NULL DEFAULT 100 CHECK (max_durability > 0);`
> 3. Create a stored procedure `use_item(p_player_id, p_item_id, p_durability_loss)` that deducts durability within an ACID transaction.
> 4. If `current_durability` reaches 0, either trigger an item break event or set an `is_broken` flag.
> 5. *Note on 3NF*: Durability belongs on `player_inventory` because individual held weapons degrade independently, whereas `max_durability` belongs on `items`.

### Question 2: "How would you implement party or guild quests?"
> **Answer**:
> 1. Create a `guilds` table (`guild_id PK, name, leader_id FK->players`).
> 2. Add `guild_id FK->guilds` to `players` table (nullable).
> 3. Create a `guild_quests` table (`guild_quest_id PK, guild_id FK, quest_id FK, status, contribution_progress JSONB`).
> 4. Implement a trigger on quest objective updates to aggregate contributions from all guild members toward the shared quest milestone.

### Question 3: "How would you migrate from Qdrant to PostgreSQL's `pgvector` extension if required?"
> **Answer**:
> 1. Enable the extension: `CREATE EXTENSION vector;`
> 2. Create table: `CREATE TABLE npc_memories (memory_id UUID PRIMARY KEY, player_id INT REFERENCES players, npc_id INT REFERENCES npcs, embedding vector(384), text TEXT, importance FLOAT, created_at TIMESTAMPTZ);`
> 3. Build an HNSW index: `CREATE INDEX ON npc_memories USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 100);`
> 4. Query using cosine distance operator `<=>`:
>    ```sql
>    SELECT text, 1 - (embedding <=> $query_vector) AS similarity
>    FROM npc_memories
>    WHERE player_id = $1 AND npc_id = $2
>    ORDER BY embedding <=> $query_vector ASC LIMIT 5;
>    ```

### Question 4: "How would you implement memory decay so NPCs forget older, trivial conversations?"
> **Answer**:
> In our retrieval scoring algorithm, apply a time-weighted exponential decay:
> $$\text{Score} = \text{Similarity} \times \exp\left(-\frac{\Delta t}{\tau}\right) \times (1 + \text{Importance})$$
> Where $\Delta t$ is the elapsed time since the memory was created, and $\tau$ is a half-life parameter. Furthermore, a scheduled database maintenance job can prune memories where $\text{Score} < \text{Threshold}$ and $\text{importance} < 0.3$.
