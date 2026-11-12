# System Architecture Specification

This document presents the complete system architecture for the **Generative NPC Memory Engine**, encompassing the full-stack infrastructure topology, context-fusion dialogue flow, multi-tenant security model, and polyglot database synchronization guarantees.

---

## 1. High-Level System Architecture

The Generative NPC Memory Engine follows a modern decoupled three-tier architecture:
1. **Presentation Layer (Frontend)**: Next.js 14 App Router, TypeScript, and Tailwind CSS.
2. **Application & Orchestration Layer (Backend)**: Python FastAPI with asynchronous connection pooling via `asyncpg`, handling business workflows, authentication, and chat context fusion.
3. **Data Layer (Polyglot Persistence)**:
   - **PostgreSQL 16**: Primary relational database for transactional game state, stored procedures, triggers, and Row-Level Security.
   - **Qdrant Vector DB**: Vector similarity engine indexing 384-dimensional dialogue memories using HNSW graph algorithms.
   - **Local / Cloud AI Inference**: `sentence-transformers` embedding generation and Google Gemini / Local Mock LLM dialogue synthesis.

```mermaid
flowchart TD
    subgraph ClientLayer["Presentation Layer (Client)"]
        UI["Next.js 14 Web Application<br/>(React, TypeScript, Tailwind CSS)"]
    end

    subgraph GatewayLayer["Application & Gateway Layer"]
        API["FastAPI Backend Server<br/>(Async ASGI, Pydantic, CORS)"]
        AuthMiddleware["JWT Authentication & RBAC Middleware"]
        ChatEngine["Chat Fusion Orchestrator"]
    end

    subgraph ServiceLayer["Inference & Intelligence Services"]
        Embedder["Embedding Engine<br/>(sentence-transformers/all-MiniLM-L6-v2)"]
        LLM["LLM Generation Service<br/>(Google Gemini API / Smart Heuristic Mock Fallback)"]
    end

    subgraph StorageLayer["Data & Persistence Layer"]
        subgraph RelationalDB["Relational Engine (PostgreSQL 16)"]
            PG_State["Game State & Economics<br/>(Players, Items, Quests, Inventory)"]
            PG_Proc["Stored Procedures & Triggers<br/>(ACID Transactions, Audit CDC)"]
            PG_RLS["Row-Level Security & RBAC<br/>(Tenant Isolation Policies)"]
        end

        subgraph VectorDB["Vector Engine (Qdrant)"]
            QD_Mem["HNSW Vector Graph Index<br/>(384-dim Cosine Distance)"]
            QD_Payload["Payload Filtering Engine<br/>(player_id, npc_id, recency)"]
        end
    end

    UI -->|"HTTPS / REST API Requests<br/>(Bearer JWT Tokens)"| API
    API --> AuthMiddleware
    AuthMiddleware --> ChatEngine

    ChatEngine -->|"1. Embed Message Text"| Embedder
    Embedder -->|"Return 384-dim Dense Vector"| ChatEngine

    ChatEngine -->|"2. Read State & Affinity (asyncpg)"| PG_State
    ChatEngine -->|"3. Filtered Vector Search"| VectorDB

    ChatEngine -->|"4. Synthesize Augmented Prompt"| LLM
    LLM -->|"Return Generated Dialogue"| ChatEngine

    ChatEngine -->|"5. Store Memory Points"| QD_Mem
    ChatEngine -->|"6. Update Affinity & Turns"| PG_Proc

    ChatEngine -->|"7. Return Dialogue Response"| UI

    classDef client fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#fff;
    classDef gateway fill:#0f172a,stroke:#818cf8,stroke-width:2px,color:#fff;
    classDef storage fill:#1e1e38,stroke:#34d399,stroke-width:2px,color:#fff;
    classDef service fill:#2a1b3d,stroke:#f472b6,stroke-width:2px,color:#fff;

    class UI client;
    class API,AuthMiddleware,ChatEngine gateway;
    class Embedder,LLM service;
    class PG_State,PG_Proc,PG_RLS,QD_Mem,QD_Payload storage;
```

---

## 2. Chat Fusion Flow Sequence

The cornerstone feature of the Generative NPC Memory Engine is the **Context Fusion Pipeline**. When a player utters a message to an NPC, the system fuses **episodic memory** (from Qdrant) with **ground-truth relational game state** (from PostgreSQL) to generate contextualized responses that acknowledge past conversations, held inventory, completed quests, and relationship affinity.

```mermaid
sequenceDiagram
    autonumber
    actor Player as Player (Client)
    participant API as FastAPI Backend
    participant Auth as Auth & RBAC
    participant PG as PostgreSQL 16
    participant Embed as Sentence-Transformers
    participant QD as Qdrant Vector DB
    participant LLM as LLM / Mock Engine

    Player->>API: POST /chat/npc (npc_id, message, session_id)
    Note over Player,API: Authorization: Bearer <JWT Token>

    API->>Auth: Validate JWT & Extract Claims
    Auth-->>API: Valid (player_id = 42, role = 'player')

    par Fetch Relational State & Embeddings
        API->>PG: Query Player State & Relationship
        Note over API,PG: SELECT gold, level, items, quests, affinity<br/>WHERE player_id = 42 AND npc_id = 2
        PG-->>API: State: Gold=250, Level=3, Bag=[Dagger], Affinity=+15.0

        API->>Embed: Embed User Utterance ("Where is the ruin?")
        Embed-->>API: 384-dimensional vector
    end

    API->>QD: Vector Search (HNSW Cosine Similarity)
    Note over API,QD: Filter: player_id = 42 AND npc_id = 2<br/>Top K = 5, with_payload = true
    QD-->>API: Top-K Relevant Memories & Timestamps

    API->>API: Assemble Augmented System Prompt
    Note over API: Fuses: NPC Persona + Relational State<br/>+ Top Memories + Affinity + User Message

    API->>LLM: Generate Dialogue (System Prompt, Context, User Prompt)
    LLM-->>API: Generated In-Character Dialogue Response

    par Store Memory & Update Affinity
        API->>QD: Upsert Dialogue Points (User + NPC turns)
        Note over API,QD: Embeddings + Payload (importance, emotion, timestamp)
        QD-->>API: Point Upsert Acknowledged

        API->>PG: Update NPC Relationship
        Note over API,PG: Increment interaction_count, update affinity_score,<br/>set last_interaction = NOW()
        PG-->>API: State Updated
    end

    API-->>Player: HTTP 200 OK (Dialogue Response, NPC Mood, Affinity Delta)
```

---

## 3. Security Architecture & Authorization

Security is enforced hierarchically across the network gateway, application middleware, and native database engine.

```mermaid
graph TD
    subgraph AuthPipeline["Defense-in-Depth Security Layers"]
        L1["Layer 1: JWT Signature & Expiration Validation (FastAPI Middleware)"]
        L2["Layer 2: Role-Based Access Control (RBAC Application Enforcers)"]
        L3["Layer 3: PostgreSQL Database Roles (app_admin, app_player)"]
        L4["Layer 4: Row-Level Security Policies (Tenant Isolation in PostgreSQL)"]
    end

    L1 --> L2 --> L3 --> L4
```

### 3.1 Token-Based Authentication (JWT)
- **Hashing**: Passwords are cryptographically salted and hashed using **Bcrypt** ($2^{12}$ rounds). Plaintext passwords are never persisted or logged.
- **Tokens**: Access tokens are signed using `HMAC-SHA256` (HS256) containing claims:
  - `sub`: Canonical username
  - `player_id`: Integer primary key identifier
  - `role`: Role string (`'player'` or `'admin'`)
  - `exp`: Short-lived expiration (e.g., 60 minutes)

### 3.2 Role-Based Access Control (RBAC)
Two primary authorization tiers are enforced:
- **`app_player`**: Can only view their own inventory, embark on quests, trade with merchants via stored procedures, and chat with NPCs.
- **`app_admin`**: Can access administrative endpoints (`/admin/*`), create or modify NPCs, grant items, inspect global audit logs, and trigger maintenance procedures.

### 3.3 Database-Level Row-Level Security (RLS)
Unlike naive applications that rely solely on application-level `WHERE player_id = X` clauses, the engine activates native **PostgreSQL Row-Level Security**:
```sql
ALTER TABLE player_inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE player_quests ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_transactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY player_inventory_isolation_policy ON player_inventory
    FOR ALL
    TO app_player
    USING (player_id = NULLIF(current_setting('app.current_player_id', true), '')::INTEGER);
```
Before executing tenant queries within an application connection, FastAPI issues:
```sql
SET LOCAL app.current_player_id = '42';
```
Even if an SQL injection vulnerability were introduced in the application layer, PostgreSQL's kernel prevents the query from seeing or modifying any inventory rows belonging to other players.

---

## 4. Polyglot Database Consistency

A critical challenge in dual-database architectures is maintaining synchronization between the relational engine (PostgreSQL) and the vector engine (Qdrant).

### 4.1 Transactional Boundaries
- **Strict Precedence**: State-changing game events (e.g., purchasing an item, claiming quest rewards) execute **exclusively** within PostgreSQL ACID transactions before vector memory is modified.
- **Idempotency**: Qdrant point IDs are deterministically generated UUIDs derived from session hashes or consecutive message IDs. Retrying a failed chat turn will overwrite the identical point ID rather than creating duplicate memory vectors.

### 4.2 Cascading Deletions & Memory Cleanup
When a player or NPC record is deleted in PostgreSQL (`ON DELETE CASCADE`), associated vector memories in Qdrant must not become orphaned.
- **Cleanup Handlers**: An administrative background task or API event handler executes Qdrant delete operations filtering by payload:
```python
await qdrant_client.delete(
    collection_name="npc_memories",
    points_selector=models.FilterSelector(
        filter=models.Filter(
            must=[models.FieldCondition(key="player_id", match=models.MatchValue(value=deleted_player_id))]
        )
    ),
)
```
- **Audit Verification**: The PostgreSQL `audit_log` records all deletions. A reconciliation worker periodically verifies that Qdrant contains zero points referencing player IDs flagged as deleted in `audit_log`.
