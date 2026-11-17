# Live SQL Demo Queries

Run these in **Admin → SQL Console** during the presentation. Paste **one query at a time** and press **Run Query** (or `Ctrl+Enter`).

How the console behaves:

| Statement | What happens |
|---|---|
| `SELECT`, `WITH`, views | Runs in a **read-only** transaction. |
| `INSERT`, `UPDATE`, `DELETE`, `CALL` | **Committed immediately**. The change shows up across the app (Market, Hunt, navbar gold, dashboards). |
| Any write with **Dry run (rollback)** ticked | Executes, shows the affected rows, then **rolls back**. Nothing is saved. |
| `UPDATE` / `DELETE` without `WHERE`, `DROP`, `TRUNCATE`, `ALTER` | **Blocked** to protect the live database. |

Tip: keep a second browser tab open on the page named in **"Show in app"** and refresh it after each write.

---

## Part 1: SELECT (reading data)

### 1. Basic filter and sort
Who are the richest players?
```sql
SELECT username, level, xp, gold, hp
FROM players
ORDER BY gold DESC;
```

### 2. JOIN: what each player owns
Three tables joined through foreign keys.
```sql
SELECT p.username, i.name AS item, i.item_type, pi.quantity, pi.is_equipped
FROM player_inventory pi
JOIN players p ON p.player_id = pi.player_id
JOIN items   i ON i.item_id   = pi.item_id
ORDER BY p.username, i.item_type;
```

### 3. GROUP BY + HAVING: inventory value per player
```sql
SELECT p.username,
       COUNT(*)                         AS distinct_items,
       SUM(pi.quantity)                 AS total_units,
       SUM(pi.quantity * i.base_price)  AS inventory_value
FROM player_inventory pi
JOIN players p ON p.player_id = pi.player_id
JOIN items   i ON i.item_id   = pi.item_id
GROUP BY p.username
HAVING SUM(pi.quantity) > 0
ORDER BY inventory_value DESC;
```

### 4. Subquery: items priced above the average
```sql
SELECT name, item_type, base_price
FROM items
WHERE base_price > (SELECT AVG(base_price) FROM items)
ORDER BY base_price DESC;
```

### 5. Window function: rank players
```sql
SELECT username, level, gold,
       RANK()       OVER (ORDER BY level DESC, xp DESC) AS level_rank,
       DENSE_RANK() OVER (ORDER BY gold DESC)           AS wealth_rank
FROM players;
```

### 6. Recursive CTE: the quest prerequisite chain
Everything you must finish before *Dragon's Awakening* (quest 8).
```sql
WITH RECURSIVE chain AS (
    SELECT qp.required_quest_id AS quest_id, 1 AS depth
    FROM quest_prerequisites qp
    WHERE qp.quest_id = 8
  UNION
    SELECT qp.required_quest_id, c.depth + 1
    FROM quest_prerequisites qp
    JOIN chain c ON qp.quest_id = c.quest_id
)
SELECT c.depth, q.quest_id, q.title, q.min_level
FROM chain c
JOIN quests q ON q.quest_id = c.quest_id
ORDER BY c.depth, q.quest_id;
```

### 7. View: the leaderboard
```sql
SELECT * FROM player_leaderboard ORDER BY leaderboard_rank;
```

### 8. Full-text search (tsvector + GIN index)
Finds items whose name or description mentions health **or** mana, ranked by relevance. Stemming means "restores" matches "restore".
```sql
SELECT name, item_type,
       ts_rank(search_vector, to_tsquery('english', 'health | mana')) AS relevance
FROM items
WHERE search_vector @@ to_tsquery('english', 'health | mana')
ORDER BY relevance DESC;
```

### 9. Combat campaign: monsters with their key and loot items
Two LEFT JOINs to the same table (`items`) with different roles.
```sql
SELECT m.name AS monster, m.region, m.min_level,
       req.name  AS key_item_needed,
       loot.name AS loot_drop, m.loot_chance
FROM monsters m
LEFT JOIN items req  ON req.item_id  = m.required_item_id
LEFT JOIN items loot ON loot.item_id = m.loot_item_id
ORDER BY m.min_level;
```

### 10. Audit trail written by triggers
```sql
SELECT log_id, table_name, operation, row_id, old_data, new_data, changed_at
FROM audit_log
ORDER BY changed_at DESC
LIMIT 10;
```

---

## Part 2: INSERT, UPDATE, DELETE (live changes)

Run 11 → 14 in order. They create a demo item, change it, then remove it, so the database ends up as it started.

### 11. INSERT: add a new item to the shop
**Show in app:** Market → Merchant Shop now lists *Presentation Blade* with "+25 Attack".
```sql
INSERT INTO items (name, description, base_price, item_type, rarity, stock, attack_power)
VALUES ('Presentation Blade', 'Forged live during the DBMS presentation.', 300, 'weapon', 'epic', 3, 25)
RETURNING item_id, name, base_price, attack_power;
```

### 12. UPDATE: put it on sale
**Show in app:** refresh the Market; the price drops to 150.
```sql
UPDATE items
SET base_price = 150, description = 'Half price, today only!'
WHERE name = 'Presentation Blade'
RETURNING name, base_price, description;
```

### 13. Verify with SELECT
The full-text search vector was refreshed automatically by the `trg_items_search_vector` trigger.
```sql
SELECT name, base_price, stock, search_vector
FROM items
WHERE name = 'Presentation Blade';
```

### 14. DELETE: remove it again
**Show in app:** refresh the Market; the item is gone.
```sql
DELETE FROM items
WHERE name = 'Presentation Blade'
RETURNING item_id, name;
```

### 15. UPDATE you can see instantly: give the admin gold
**Show in app:** the gold counter in the top navbar changes as soon as the query finishes.
```sql
UPDATE players
SET gold = gold + 500
WHERE username = 'admin'
RETURNING username, gold;
```
Then show that the `trg_audit_players_gold` trigger recorded it:
```sql
SELECT table_name, operation, old_data->>'gold' AS old_gold, new_data->>'gold' AS new_gold, changed_at
FROM audit_log
WHERE table_name = 'players'
ORDER BY changed_at DESC
LIMIT 3;
```
To undo it afterwards:
```sql
UPDATE players SET gold = gold - 500 WHERE username = 'admin' RETURNING username, gold;
```

### 16. DELETE with a condition: clear abandoned battles
Removes battle history where the player ran away (harmless; only history rows).
```sql
DELETE FROM battles
WHERE status = 'fled'
RETURNING battle_id, player_id, monster_id, started_at;
```

---

## Part 3: Constraints, triggers and transactions

### 17. CHECK constraint / trigger blocks negative gold
Expected result: **error**, and nothing changes.
```sql
UPDATE players SET gold = -10 WHERE username = 'hero';
```

### 18. Trigger: automatic level-up (tick **Dry run** first)
Adding XP makes `trg_auto_level_up` recalculate the level. With Dry run ticked you see the new level, then it is rolled back.
```sql
UPDATE players
SET xp = xp + 5000
WHERE username = 'hero'
RETURNING username, xp, level;
```

### 19. Stored procedure with ACID rollback: not enough gold
`buy_item` locks the player row (`SELECT ... FOR UPDATE`), checks gold and stock, and raises an error. The whole transaction rolls back.
Expected result: **error** ("insufficient gold"); hero's gold is unchanged.
```sql
CALL buy_item(2, 2, 1);
```

### 20. Stored procedure that succeeds (tick **Dry run** to keep data unchanged)
Hero (player 2) buys one Elixir of Vitality (item 5). Without Dry run this really happens: gold drops by 25 and the item appears in hero's vault and ledger.
```sql
CALL buy_item(2, 5, 1);
```

### 21. Dry run of a dangerous delete
Tick **Dry run**, then run this. It reports **1 row affected** and rolls back; query 1 still shows the player.
```sql
DELETE FROM players WHERE username = 'mage';
```

### 22. Safety guard
Expected result: **blocked** with "DELETE without a WHERE clause is blocked".
```sql
DELETE FROM battles;
```
