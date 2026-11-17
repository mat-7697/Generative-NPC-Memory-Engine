-- ============================================================================
-- Migration 008: Combat Campaign ("Seal the Void Rift")
-- Gives gear a purpose: weapons add attack, armor adds defense, potions heal.
-- Adds monsters across 7 regions, a persistent HP pool, server-side battles,
-- and a kill ledger. Idempotent: safe to run more than once.
-- ============================================================================

-- 1. Item combat stats -------------------------------------------------------
ALTER TABLE items ADD COLUMN IF NOT EXISTS attack_power  INTEGER NOT NULL DEFAULT 0 CHECK (attack_power  >= 0);
ALTER TABLE items ADD COLUMN IF NOT EXISTS defense_power INTEGER NOT NULL DEFAULT 0 CHECK (defense_power >= 0);
ALTER TABLE items ADD COLUMN IF NOT EXISTS heal_amount   INTEGER NOT NULL DEFAULT 0 CHECK (heal_amount   >= 0);

UPDATE items SET attack_power = 8   WHERE name = 'Iron Longsword';
UPDATE items SET attack_power = 40  WHERE name = 'Dragonbone Greatsword';
UPDATE items SET defense_power = 6  WHERE name = 'Steel Breastplate';
UPDATE items SET defense_power = 18 WHERE name = 'Robes of the Nethermancer';
UPDATE items SET heal_amount = 40   WHERE name = 'Elixir of Vitality';
UPDATE items SET heal_amount = 30   WHERE name = 'Mana Draught';      -- also doubles your next hit in battle
UPDATE items SET heal_amount = 999  WHERE name = 'Starfall Phial';    -- full heal

UPDATE items SET description = 'Thick fur dropped by Timber Wolves in the Whispering Woods. Sell it to the merchant for gold.'
WHERE name = 'Timber Wolf Pelt';
UPDATE items SET description = 'An ornate iron key inscribed with necromantic wards. Opens the Crypt of Karaz hunting ground. Earned from the quest "The Ancient Crypt".'
WHERE name = 'Crypt Key of Karaz';
UPDATE items SET description = 'A pulsating crystalline core torn from a Void Cult Champion. Opens the path to the Ashen Wyrm atop the Mount of Ash.'
WHERE name = 'Heart of the Void';
UPDATE items SET description = 'A shimmering mana tonic. Restores 30 HP and, in battle, doubles the damage of your next attack.'
WHERE name = 'Mana Draught';
UPDATE items SET description = 'A celestial concoction that fully restores your health. Save it for the hardest fights.'
WHERE name = 'Starfall Phial';

-- 2. Persistent player health -------------------------------------------------
ALTER TABLE players ADD COLUMN IF NOT EXISTS hp INTEGER NOT NULL DEFAULT 100 CHECK (hp >= 0);

-- 3. Monsters -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS monsters (
    monster_id INTEGER PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    region VARCHAR(100) NOT NULL,
    description TEXT,
    icon VARCHAR(16) NOT NULL DEFAULT '👾',
    min_level INTEGER NOT NULL DEFAULT 1 CHECK (min_level > 0),
    required_item_id INTEGER REFERENCES items(item_id) ON DELETE SET NULL,
    max_hp INTEGER NOT NULL CHECK (max_hp > 0),
    attack INTEGER NOT NULL CHECK (attack >= 0),
    defense INTEGER NOT NULL CHECK (defense >= 0),
    gold_reward INTEGER NOT NULL DEFAULT 0 CHECK (gold_reward >= 0),
    xp_reward INTEGER NOT NULL DEFAULT 0 CHECK (xp_reward >= 0),
    loot_item_id INTEGER REFERENCES items(item_id) ON DELETE SET NULL,
    loot_chance NUMERIC(4,3) NOT NULL DEFAULT 0 CHECK (loot_chance BETWEEN 0 AND 1),
    is_boss BOOLEAN NOT NULL DEFAULT FALSE
);

INSERT INTO monsters (monster_id, name, region, description, icon, min_level, required_item_id, max_hp, attack, defense, gold_reward, xp_reward, loot_item_id, loot_chance, is_boss) VALUES
(1, 'Dire Rat',           'Whispering Crow Cellar', 'Oversized vermin gnawing through the inn''s winter stores. A good first fight.', '🐀', 1, NULL, 30,  7,  0,  12,   25,  5,  0.15, FALSE),
(2, 'Timber Wolf',        'Whispering Woods',       'Hunts in packs along the forest road. Its pelt sells well at the market.',      '🐺', 2, NULL, 60,  11, 2,  20,   45,  8,  0.70, FALSE),
(3, 'Dock Smuggler',      'Canal Docks',            'A knife-wielding thug guarding contraband crates beneath the docks.',           '🗡️', 3, NULL, 90,  15, 5,  40,   80,  5,  0.35, FALSE),
(4, 'Stone Golem',        'Iron Mines',             'Animated rock blocking the iron veins Gorim needs. Hard to hurt without a blade.', '🪨', 4, NULL, 140, 20, 12, 70,   130, 6,  0.30, FALSE),
(5, 'Barrow Wight',       'Crypt of Karaz',         'A restless dead lord. The crypt is sealed: you need the Crypt Key of Karaz.',   '💀', 5, 9,    190, 26, 14, 120,  220, 6,  0.40, FALSE),
(6, 'Void Cult Champion', 'Void Rift Gate',         'Elite guardian of the rift. Said to carry the Heart of the Void.',              '🌀', 6, NULL, 260, 32, 18, 200,  380, 10, 0.35, FALSE),
(7, 'Ashen Wyrm',         'Mount of Ash',           'The ancient dragon feeding the rift. Defeat it to seal the Void Rift for good.', '🐉', 8, 10,   700, 48, 26, 3000, 4000, 7, 1.00, TRUE)
ON CONFLICT (monster_id) DO NOTHING;

-- 4. Battles (one active battle per player, enforced by a partial unique index)
CREATE TABLE IF NOT EXISTS battles (
    battle_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    monster_id INTEGER NOT NULL REFERENCES monsters(monster_id) ON DELETE CASCADE,
    monster_hp INTEGER NOT NULL CHECK (monster_hp >= 0),
    status VARCHAR(10) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'won', 'lost', 'fled')),
    empowered BOOLEAN NOT NULL DEFAULT FALSE,
    turns INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_battles_one_active_per_player
    ON battles(player_id) WHERE status = 'active';

-- 5. Kill ledger ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS player_monster_kills (
    player_id INTEGER NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    monster_id INTEGER NOT NULL REFERENCES monsters(monster_id) ON DELETE CASCADE,
    kills INTEGER NOT NULL DEFAULT 0 CHECK (kills >= 0),
    first_kill_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (player_id, monster_id)
);

-- 6. Allow the new ledger entry types ------------------------------------------
DO $$
DECLARE c TEXT;
BEGIN
    FOR c IN
        SELECT conname FROM pg_constraint
        WHERE conrelid = 'inventory_transactions'::regclass AND contype = 'c'
          AND pg_get_constraintdef(oid) LIKE '%transaction_type%'
    LOOP
        EXECUTE format('ALTER TABLE inventory_transactions DROP CONSTRAINT %I', c);
    END LOOP;
END $$;

ALTER TABLE inventory_transactions ADD CONSTRAINT inventory_transactions_transaction_type_check
    CHECK (transaction_type IN ('buy', 'sell', 'transfer_in', 'transfer_out', 'quest_reward',
                                'admin_grant', 'consume_item', 'battle_loot', 'inn_rest'));

-- 7. Only one weapon and one armor piece may be equipped: reset duplicates.
UPDATE player_inventory pi SET is_equipped = FALSE
FROM items i
WHERE pi.item_id = i.item_id AND pi.is_equipped AND i.item_type NOT IN ('weapon', 'armor');

-- 8. Start everyone at full health for their level (max HP = 90 + 10 x level).
UPDATE players SET hp = 90 + 10 * level;
