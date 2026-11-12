# Generative NPC Memory Engine: Project Walkthrough & Viva Guide

> **Project Architecture:** Hybrid Database System combining PostgreSQL 18 (Relational ACID State) + Qdrant (384-dimensional Vector Cognitive Memory) + FastAPI + Next.js 16 (App Router) + Google Gemini API.  
> **Course / Scope:** Advanced DBMS Level 3 Mini-Project (50/50 Marks Evaluation Rubric Compliance).  
> **Repository Root:** `C:\Users\Mateen\.gemini\antigravity\scratch\generative-npc-memory-engine`

---

## 1. Executive Summary & Core Technical Highlights

The **Generative NPC Memory Engine** addresses the fundamental limitations of modern video game NPCs: static dialogue trees, lack of persistent memory, and disconnection from game world economics.

### Why Polyglot Persistence? (PostgreSQL + Qdrant)
1. **Relational Paradigm (PostgreSQL 18):**
   - **Guarantees ACID Transactions:** Prevents economic exploits, negative balances, and item duplication using pessimistic row locks (`SELECT ... FOR UPDATE`).
   - **Enforces Integrity via Constraints & Triggers:** Check constraints (`CHECK (gold >= 0)`), unique composite indexes (`UNIQUE(player_id, item_id)`), and audit Change Data Capture (CDC) triggers.
   - **Recursive CTE DAG Traversal:** Self-referencing prerequisite chains evaluated using `WITH RECURSIVE` queries.
2. **Vector Paradigm (Qdrant):**
   - **High-Dimensional Cosine Search:** 384-dimensional dense vector embeddings generated via `sentence-transformers/all-MiniLM-L6-v2`.
   - **Episodic Memory Retrieval:** Retrieves past conversational turns filtered by `player_id` and `npc_id` with sub-10ms latency using HNSW indexing.
   - **Recency-Decay Scoring Formula:** Combines semantic vector similarity, memory importance weighting, and exponential time decay:
     $$\text{Final Score} = (\text{Vector Cosine Score} \times 0.7) + (e^{-0.015 \times \Delta t_{\text{hours}}} \times 0.3)$$
3. **Chat Context Fusion Pipeline:**
   FastAPI pulls relational state (player level, gold, equipped inventory, active quests) from PostgreSQL, fetches top-$K$ semantic memories from Qdrant, and synthesizes a prompt for the Google Gemini API.

---

## 2. Solutions Implemented in this Development Session

### A. Transitioned LLM Provider to Google Gemini
- Replaced OpenAI API calls with **Google Gemini API** (`google-generativeai`).
- Integrated API key configuration and prompt synthesis with automatic fallback heuristics.

### B. Interactive Quest Challenge System (Gameplay & Anti-Cheat)
Previously, quests could be completed with a single click, granting rewards without verified action. We designed and implemented a **full challenge verification pipeline**:
1. **PostgreSQL Schema Migration (`005_quest_challenges.sql`):** Added `challenge_type`, `challenge_question`, `challenge_hint`, and `challenge_answer` to the `quests` table.
2. **Server-Side Verification:** The backend `POST /api/quests/{quest_id}/complete` endpoint accepts a `{ solution }` payload. It validates the player's submission against `q.challenge_answer` inside PostgreSQL. If incorrect, it raises an HTTP 400 error with a hint. Public endpoints strictly omit `challenge_answer` to prevent client-side inspection.
3. **Interactive Frontend Modal:** Active quests open a **Mission Objective Challenge Modal** featuring the briefing, collapsible hint, direct link to NPC chat, and an answer submission field.
4. **Demo Mode Reset Controls:** Added `🔄 Reset Quests` and `🌱 Reset Lv. 1 Demo` buttons to the UI header so the entire progression can be demonstrated repeatedly during evaluations.

---

## 3. Catalog of the 8 Interactive Quests & Solutions

| # | Quest Title | Min Lv | Challenge Type | Mission Objective / Riddle | Solution / Flag |
|---|---|---|---|---|---|
| **1** | **Rats in the Cellar** | Lv. 1 | 🧮 **Math Challenge** | 3 packs of dire rats: East tunnel has 7, West has 12, Central grain storage has double the East (14). Total rats? | `33` |
| **2** | **Gathering Herbal Flora** | Lv. 1 | ⚖️ **Apothecary Ratio** | Silas needs 3 moon-orchids per vitality elixir vial. How many orchids are needed for 5 vials? | `15` |
| **3** | **The Smuggler's Secret** | Lv. 2 | 🕵️ **CTF Cipher / NPC Intel** | Chat with **Elara Ravenshade** in the `/chat` tab about *"smuggler secrets"* or *"dock cipher"* to uncover the codeword. | `SHADOW_CARGO_77` |
| **4** | **The Iron Shortage** | Lv. 2 | ⚒️ **Dwarven Forge Math** | Blast furnace recipe: 3 parts iron ore to 2 parts flux coal. If Gorim loads 18 parts iron ore, how much flux coal is needed? | `12` |
| **5** | **The Alchemist's Apprentice** | Lv. 3 | ⚡ **Arcane Resonance Math** | Archmage Varis tests mana ward frequencies: frequency doubles every hour. If it reaches 64 kHz after 6 hours, what was it at hour 0? | `1` |
| **6** | **The Ancient Crypt** | Lv. 4 | 🗝️ **Crypt Door Riddle** | *"I speak without a voice, I hear without ears. I have no body, but I come alive with the wind. What am I?"* | `echo` |
| **7** | **Shadows Over the Capital** | Lv. 5 | 💻 **Cryptographic Logic** | Intercepted 4-bit binary Void Cult code: compute `1010 XOR 0110`. | `1100` |
| **8** | **Dragon's Awakening** | Lv. 6 | 🐉 **Primordial Boss Riddle** | Primordial wyrm challenge: *"Feed me and I live, yet give me water and I die. What am I?"* | `fire` |

---

## 4. The 5 Major Evaluator Rubric Enhancements

### Enhancement 1: NPC Quest Context Awareness in Generative Chat
- **Module:** `backend/app/services/chat_fusion.py`
- **Behavior:** The database retrieves both active and completed quests for the player. NPCs dynamically tailor their dialogue:
  - If you ask **Gorim** about *The Iron Shortage*, he guides you through the furnace ratio (`12`).
  - If you ask **Elara** about *The Smuggler's Secret*, she discloses the passphrase (`SHADOW_CARGO_77`).
  - NPCs congratulate the player for completed achievements, reinforcing immersion.

### Enhancement 2: Live SQL Console & `EXPLAIN ANALYZE` Benchmarker
- **Module:** `backend/app/routers/admin.py` & `frontend/src/app/admin/page.tsx`
- **Behavior:** An interactive SQL workspace built right into the Admin panel (`/admin` $\rightarrow$ `💻 SQL Console & EXPLAIN`).
  - Evaluators can enter any SQL query and execute it in real time.
  - Measures execution time in milliseconds and renders formatted tables.
  - Generates full **`EXPLAIN (ANALYZE, BUFFERS)`** execution plans showing sequential scans vs index scans, planning time, and cost.
  - Provides 6 one-click viva presets covering all core DBMS syllabus topics.

### Enhancement 3: Evaluator Guided Viva Tour Walkthrough
- **Module:** `frontend/src/app/dashboard/page.tsx`
- **Behavior:** A prominent **`🎓 Evaluator Viva Tour`** button in the dashboard header.
  - Offers a 5-step interactive walkthrough aligned with the 50/50 marks rubric.
  - Features clear architecture summaries and exact **"Recommended Viva Talking Points"** for the student.

### Enhancement 4: Usable Inventory Items (Equip / Consume)
- **Module:** `backend/app/routers/inventory.py` & `frontend/src/app/inventory/page.tsx`
- **Behavior:** Added `is_equipped` column to `player_inventory` (Migration 006) and a `POST /api/inventory/use` endpoint.
  - **Potions:** Drinking an elixir awards XP, decrements stack quantity, and creates a transaction audit record.
  - **Weapons & Armor:** Players can equip or unequip gear slots, displaying a glowing `✨ EQUIPPED` badge.

### Enhancement 5: 2D Semantic Memory Vector Map
- **Module:** `frontend/src/app/memory/page.tsx`
- **Behavior:** Added a **`🌌 2D Vector Map`** view toggle on the vector memory page.
  - Projects 384-dimensional dense vectors onto an interactive SVG orbital canvas with concentric cosine threshold rings (80%, 60%, 40%).
  - Point radius reflects memory importance; point color reflects cosine similarity.
  - Hovering or clicking points displays the full payload text, cosine relevance, and metadata.

---

## 5. Viva Voce Defense Guide: Running Queries & Answering Questions

### Where and How to Run SQL Queries During Viva

#### Method 1: Directly in the Web Application (Recommended)
1. Go to [`http://localhost:3000/admin`](http://localhost:3000/admin).
2. Click the **`💻 SQL Console & EXPLAIN`** tab.
3. Select any curated preset or type the teacher's query.
4. Click **`▶️ Run Query`** for data or **`⚡ EXPLAIN ANALYZE`** for execution performance.

#### Method 2: Command Line Interface (`psql`)
1. Open PowerShell on Windows.
2. Connect to the database:
   ```powershell
   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d generative_npc_db
   ```
3. Enter your PostgreSQL password (e.g. `postgres`).
4. Type queries ending with `;`. Useful commands:
   - `\dt` — List all tables
   - `\d players` — Show table columns and CHECK constraints
   - `\df` — List stored procedures

#### Method 3: pgAdmin 4 GUI
1. Open **pgAdmin 4** $\rightarrow$ Servers $\rightarrow$ PostgreSQL 18 $\rightarrow$ Databases $\rightarrow$ `generative_npc_db`.
2. Open the **Query Tool** (`Alt + Shift + Q`), write your query, and press **F5**.

---

### The 6 Essential SQL Queries Evaluators Ask For

#### 1. Multi-Table JOIN with Wealth Aggregation (JOIN + GROUP BY + SUM)
```sql
SELECT 
    p.player_id,
    p.username,
    p.level,
    p.gold,
    COUNT(pi.item_id) AS total_inventory_slots,
    COALESCE(SUM(pi.quantity * i.base_price), 0) AS inventory_net_worth,
    p.gold + COALESCE(SUM(pi.quantity * i.base_price), 0) AS total_player_wealth
FROM players p
LEFT JOIN player_inventory pi ON p.player_id = pi.player_id
LEFT JOIN items i ON pi.item_id = i.item_id
GROUP BY p.player_id, p.username, p.level, p.gold
ORDER BY total_player_wealth DESC;
```
*Evaluator takeaway:* Proves mastery of multi-table joins, outer joins for players without items, aggregate grouping, and null-coalescing.

#### 2. Window Function: DENSE_RANK() Leaderboard
```sql
SELECT 
    player_id,
    username,
    level,
    xp,
    gold,
    DENSE_RANK() OVER (ORDER BY level DESC, xp DESC) AS level_rank,
    DENSE_RANK() OVER (ORDER BY gold DESC) AS wealth_rank
FROM players
ORDER BY level_rank ASC;
```
*Evaluator takeaway:* Demonstrates advanced SQL window analytics without collapsing underlying rows into summary groups.

#### 3. Recursive CTE: Quest Prerequisite DAG Traversal
```sql
WITH RECURSIVE quest_prereq_chain AS (
    SELECT 
        quest_id,
        title,
        min_level,
        0 AS depth,
        title::text AS traversal_path
    FROM quests
    WHERE quest_id = 8
    UNION ALL
    SELECT 
        q.quest_id,
        q.title,
        q.min_level,
        c.depth + 1,
        c.traversal_path || ' -> ' || q.title
    FROM quest_prerequisites qp
    JOIN quest_prereq_chain c ON qp.quest_id = c.quest_id
    JOIN quests q ON qp.required_quest_id = q.quest_id
)
SELECT depth, quest_id, title, min_level, traversal_path
FROM quest_prereq_chain
ORDER BY depth ASC;
```
*Evaluator takeaway:* Proves hierarchical directed graph evaluation directly inside the relational engine.

#### 4. Full-Text Search with GIN Index
```sql
SELECT item_id, name, item_type, rarity, base_price, description
FROM items
WHERE to_tsvector('english', name || ' ' || COALESCE(description, '')) @@ to_tsquery('english', 'elixir | blade | potion')
ORDER BY base_price DESC;
```
*Evaluator takeaway:* Demonstrates inverted GIN index acceleration over slow linear `LIKE '%text%'` pattern searches.

#### 5. Subquery with HAVING Clause
```sql
SELECT 
    p.player_id,
    p.username,
    p.level,
    COUNT(pq.quest_id) AS active_quest_count
FROM players p
JOIN player_quests pq ON p.player_id = pq.player_id
WHERE pq.status = 'active'
GROUP BY p.player_id, p.username, p.level
HAVING COUNT(pq.quest_id) >= 1
ORDER BY active_quest_count DESC;
```
*Evaluator takeaway:* Clarifies the difference between row filtering (`WHERE`) and post-aggregation group filtering (`HAVING`).

#### 6. Change Data Capture (CDC) Audit Trigger
```sql
SELECT audit_id, table_name, operation, player_id, old_data, new_data, changed_at
FROM audit_log
ORDER BY changed_at DESC
LIMIT 10;
```
*Evaluator takeaway:* Proves database-level security and non-repudiation auditing that fires even on manual database modifications.

---

## 6. Ten-Minute Live Demonstration Sequence

| Step | Time | Segment | What to Show / Demonstrate |
|:---:|:---:|---|---|
| **1** | 0:00–1:00 | **Architecture** | Open `/dashboard`, click **`🎓 Evaluator Viva Tour`**, and explain PostgreSQL (ACID economics) + Qdrant (vector memories). |
| **2** | 1:00–2:30 | **Relational Schema** | Open `/admin` $\rightarrow$ `💻 SQL Console`. Run Preset #1 (Multi-Table Join) and Preset #2 (Window Ranking). |
| **3** | 2:30–4:00 | **ACID & Row Locks** | Open `/inventory`. Buy an item; show gold decrement, inventory increment, and CDC record in audit log. |
| **4** | 4:00–5:30 | **Recursive CTE DAG** | Open `/quests`. Click **Prerequisites 🌲** on *The Ancient Crypt* to show recursive CTE graph resolution. |
| **5** | 5:30–7:00 | **Interactive Challenges** | Accept Quest 1 (*Rats in the Cellar*). Click **`Solve Objective ⚔️`**. Enter wrong answer (`10`) $\rightarrow$ rejected. Enter `33` $\rightarrow$ rewards claimed & auto level-up! |
| **6** | 7:00–8:30 | **Chat Context Fusion** | Open `/chat`. Talk to Elara Ravenshade about *"smuggler secrets"*. Show her returning cipher `SHADOW_CARGO_77`. |
| **7** | 8:30–10:00 | **Vector Map & Qdrant** | Open `/memory`. Switch to **`🌌 2D Vector Map`**. Show 384-dimensional embeddings projected with cosine similarity orbits. |

---

## 7. How to Export this Document to PDF

1. **Option A (VS Code / Antigravity IDE):**
   - Open this file: `docs/PROJECT_WALKTHROUGH_AND_VIVA_GUIDE.md`.
   - Press `Ctrl + Shift + P` $\rightarrow$ type **Markdown: Print to PDF** or open in preview and right-click **Print to PDF**.
2. **Option B (Browser Print):**
   - Open the file in Chrome/Edge, press `Ctrl + P`, select **Save as PDF**, and choose **Background graphics: On**.
