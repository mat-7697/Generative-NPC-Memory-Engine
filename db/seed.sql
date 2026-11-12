-- ============================================================================
-- Generative NPC Memory Engine - Comprehensive Seed Data
-- Project: Generative NPC Memory Engine (PES University DBMS Mini-Project)
-- File: db/seed.sql
-- Description: Realistic initial dataset seeding administrative accounts, players,
--              LLM-ready NPC personas with Big-Five personality traits, multi-tier
--              items catalog, complex quest prerequisite DAGs, inventories,
--              quest states, sentiment relationships, and transactional ledgers.
-- ============================================================================

BEGIN;

-- Temporarily disable triggers if needed, or allow triggers to populate search vectors & timestamps
-- Triggers will cleanly compute search_vectors for items and quests.

-- ----------------------------------------------------------------------------
-- 1. SEED PLAYERS (Admin, Hero, Mage)
-- Passwords:
--   admin -> 'admin123'
--   hero  -> 'hero123'
--   mage  -> 'mage123'
-- ----------------------------------------------------------------------------
INSERT INTO players (player_id, username, email, password_hash, role, gold, level, xp, created_at, updated_at)
OVERRIDING SYSTEM VALUE
VALUES 
(1, 'admin', 'admin@realm.org', '$2b$12$hYC0zvE6erGorVS6xYnaAO054SN7IXrh5H04k55B2nL.6ktIqnWwC', 'admin', 5000, 20, 50000, NOW() - INTERVAL '30 days', NOW() - INTERVAL '1 hour'),
(2, 'hero', 'hero@adventurer.io', '$2b$12$wx9dKpUTeaqAMWMovoCPOuisXtKXwjzAi.bnVePrp.s/Y.XY6XsbS', 'player', 350, 4, 1850, NOW() - INTERVAL '14 days', NOW() - INTERVAL '3 hours'),
(3, 'mage', 'mage@arcane.edu', '$2b$12$CFH2nXUaaSgsrmrfgkimR.20MR0A7xthmLU2yWGKnfu0TlESLrT/S', 'player', 780, 6, 4200, NOW() - INTERVAL '10 days', NOW() - INTERVAL '30 minutes');

-- Synchronize identity sequence for players
ALTER TABLE players ALTER COLUMN player_id RESTART WITH 4;


-- ----------------------------------------------------------------------------
-- 2. SEED NPCS (5 Diverse Personas with Structured JSONB Personality Traits)
-- ----------------------------------------------------------------------------
INSERT INTO npcs (npc_id, name, persona, location, personality_traits, greeting, created_at)
OVERRIDING SYSTEM VALUE
VALUES
(
    1,
    'Gorim Ironbreaker',
    'A gruff dwarven master smith whose hammer has forged armaments for kings and champions. Proud of his craft, blunt in speech, but possesses unwavering loyalty to those who treat forged steel with respect.',
    'The Obsidian Forge, Iron District',
    '{
        "archetype": "blacksmith",
        "openness": 0.40,
        "conscientiousness": 0.95,
        "extraversion": 0.35,
        "agreeableness": 0.55,
        "neuroticism": 0.20,
        "speech_style": "gruff, direct, punctuated by rhythmic hammer strikes",
        "voice_pitch": "deep_baritone",
        "core_values": ["craftsmanship", "honesty", "resilience"]
    }'::jsonb,
    'Keep your paws off the tempered blade unless you have the coin to honor true dwarven steel!',
    NOW() - INTERVAL '20 days'
),
(
    2,
    'Elara Ravenshade',
    'Former rogue of the Shadow Guild, now proprietress of the Whispering Crow Inn. Master of rumor diplomacy, observant of political tides, and discreet with secrets.',
    'The Whispering Crow Inn, Old Town',
    '{
        "archetype": "innkeeper",
        "openness": 0.88,
        "conscientiousness": 0.72,
        "extraversion": 0.82,
        "agreeableness": 0.70,
        "neuroticism": 0.30,
        "speech_style": "conspiratorial, warm, melodious, subtle",
        "voice_pitch": "soft_alto",
        "core_values": ["intelligence", "hospitality", "subtlety"]
    }'::jsonb,
    'Pull up a chair near the hearth, friend. The mead is chilled, and my ears are always attuned to fresh tidings.',
    NOW() - INTERVAL '20 days'
),
(
    3,
    'Archmage Varis',
    'An ancient High-Elven arcanist and headmaster of the Spire of Arcanum. Preoccupied with celestial alignment calculations and dimensional rifts.',
    'Arcanum Observatory, High Spire',
    '{
        "archetype": "wizard",
        "openness": 0.98,
        "conscientiousness": 0.85,
        "extraversion": 0.25,
        "agreeableness": 0.50,
        "neuroticism": 0.45,
        "speech_style": "academic, archaic, precise, mildly condescending",
        "voice_pitch": "refined_tenor",
        "core_values": ["knowledge", "cosmic_order", "erudition"]
    }'::jsonb,
    'Enter carefully. The ley-line harmonics are fragile today, and I have little patience for frivolous interruptions.',
    NOW() - INTERVAL '20 days'
),
(
    4,
    'Silas Goldleaf',
    'A flamboyant merchant prince from the eastern silk trade. Believes every diplomatic deadlock can be resolved with balanced commerce and high-margin goods.',
    'Grand Bazaar, Stall 14',
    '{
        "archetype": "merchant",
        "openness": 0.78,
        "conscientiousness": 0.80,
        "extraversion": 0.92,
        "agreeableness": 0.68,
        "neuroticism": 0.15,
        "speech_style": "theatrical, enthusiastic, charming, persuasive",
        "voice_pitch": "lively_tenor",
        "core_values": ["wealth", "negotiation", "luxury"]
    }'::jsonb,
    'Welcome, patron of discerning elegance! Behold genuine curiosities gathered from beyond the Sunken Sea!',
    NOW() - INTERVAL '20 days'
),
(
    5,
    'Captain Roland',
    'A disciplined veteran captain commanding the Citadel Guard. Dedicated to peacekeeping, martial drills, and civilian welfare against marauder threats.',
    'Citadel Guardhouse & Ramparts',
    '{
        "archetype": "guard_captain",
        "openness": 0.35,
        "conscientiousness": 0.98,
        "extraversion": 0.55,
        "agreeableness": 0.45,
        "neuroticism": 0.20,
        "speech_style": "authoritative, brief, disciplined, alert",
        "voice_pitch": "commanding_bass",
        "core_values": ["duty", "law", "protection"]
    }'::jsonb,
    'Hold citizen. Maintain the peace within these walls and report any suspicious cultist movements at once.',
    NOW() - INTERVAL '20 days'
);

ALTER TABLE npcs ALTER COLUMN npc_id RESTART WITH 6;


-- ----------------------------------------------------------------------------
-- 3. SEED ITEMS (10 Items spanning all types and rarities)
-- ----------------------------------------------------------------------------
INSERT INTO items (item_id, name, description, base_price, item_type, rarity, stock, created_at)
OVERRIDING SYSTEM VALUE
VALUES
(1, 'Iron Longsword', 'A standard-issue double-edged military blade balanced for infantry skirmishes.', 50, 'weapon', 'common', 25, NOW() - INTERVAL '15 days'),
(2, 'Dragonbone Greatsword', 'Forged from the calcified femur of an ancient wyrm. Emits faint thermal embers when wielded.', 2500, 'weapon', 'legendary', 1, NOW() - INTERVAL '15 days'),
(3, 'Steel Breastplate', 'Reinforced steel cuirass offering solid deflection against slashing blades and crossbow bolts.', 180, 'armor', 'uncommon', 10, NOW() - INTERVAL '15 days'),
(4, 'Robes of the Nethermancer', 'Silken vestments woven with shadow-silk that amplify void spell potency and mana absorption.', 1800, 'armor', 'epic', 2, NOW() - INTERVAL '15 days'),
(5, 'Elixir of Vitality', 'A shimmering crimson tincture that restores health and closes puncture wounds rapidly.', 25, 'potion', 'common', 100, NOW() - INTERVAL '15 days'),
(6, 'Mana Draught', 'Infused with distilled azure mana blooms to rapidly replenish depleted arcane pools.', 45, 'potion', 'uncommon', 75, NOW() - INTERVAL '15 days'),
(7, 'Starfall Phial', 'A celestial concoction granting brief invulnerability and heightened critical strike chance.', 350, 'potion', 'rare', 8, NOW() - INTERVAL '15 days'),
(8, 'Timber Wolf Pelt', 'Thick fur harvested from northern timber wolves. Valued by armorers and leatherworkers.', 15, 'misc', 'common', 150, NOW() - INTERVAL '15 days'),
(9, 'Crypt Key of Karaz', 'An ornate iron key inscribed with necromantic wards. Unlocks the subterranean vault beneath the barrows.', 1, 'quest_item', 'rare', -1, NOW() - INTERVAL '15 days'),
(10, 'Heart of the Void', 'A pulsating crystalline core radiating primordial cosmic energy. Essential for stabilizing the planar rift.', 1, 'quest_item', 'legendary', -1, NOW() - INTERVAL '15 days');

ALTER TABLE items ALTER COLUMN item_id RESTART WITH 11;


-- ----------------------------------------------------------------------------
-- 4. SEED QUESTS (8 Quests forming a structured prerequisite DAG)
-- ----------------------------------------------------------------------------
INSERT INTO quests (quest_id, title, description, reward_gold, reward_xp, reward_item_id, min_level, quest_type, created_at)
OVERRIDING SYSTEM VALUE
VALUES
(1, 'Rats in the Cellar', 'Clear the Whispering Crow Inn cellar of aggressive dire rodents threatening winter food reserves.', 50, 100, 5, 1, 'side', NOW() - INTERVAL '12 days'),
(2, 'Gathering Herbal Flora', 'Forage rare moon-orchids and silverleaf herbs from the Whispering Woods for the local apothecary.', 40, 80, 8, 1, 'side', NOW() - INTERVAL '12 days'),
(3, 'The Smuggler''s Secret', 'Investigate covert illicit shipments passing through the canal vaults beneath the docks.', 120, 250, 3, 2, 'side', NOW() - INTERVAL '12 days'),
(4, 'The Iron Shortage', 'Secure the goblin-infested hillside iron mine to restore vital ore supplies to the Obsidian Forge.', 150, 300, 1, 2, 'side', NOW() - INTERVAL '12 days'),
(5, 'The Alchemist''s Apprentice', 'Assist Master Silas and Elara in concocting a protective ward using gathered herbs and covert documents.', 300, 700, 6, 3, 'main', NOW() - INTERVAL '12 days'),
(6, 'The Ancient Crypt', 'Enter the forgotten crypt of Karaz and recover the lost ceremonial seal of the First Kingdom.', 450, 1100, 9, 4, 'main', NOW() - INTERVAL '12 days'),
(7, 'Shadows Over the Capital', 'Unmask high-ranking noble conspirators conspiring with the Void Cult inside the Citadel.', 800, 2000, 7, 5, 'main', NOW() - INTERVAL '12 days'),
(8, 'Dragon''s Awakening', 'Confront the resurrected primordial wyrm atop the Mount of Ash and salvage its heart.', 2500, 5000, 2, 6, 'main', NOW() - INTERVAL '12 days');

ALTER TABLE quests ALTER COLUMN quest_id RESTART WITH 9;


-- ----------------------------------------------------------------------------
-- 5. SEED QUEST PREREQUISITES (DAG Dependencies)
-- Graph Structure:
--   Quest 3 -> requires Quest 1
--   Quest 4 -> requires Quest 1
--   Quest 5 -> requires Quest 2 AND Quest 3
--   Quest 6 -> requires Quest 4
--   Quest 7 -> requires Quest 5
--   Quest 8 -> requires Quest 5 AND Quest 6
-- ----------------------------------------------------------------------------
INSERT INTO quest_prerequisites (prerequisite_id, quest_id, required_quest_id)
OVERRIDING SYSTEM VALUE
VALUES
(1, 3, 1),  -- Smuggler's Secret requires Rats in the Cellar
(2, 4, 1),  -- Iron Shortage requires Rats in the Cellar
(3, 5, 2),  -- Alchemist's Apprentice requires Gathering Herbs
(4, 5, 3),  -- Alchemist's Apprentice requires Smuggler's Secret
(5, 6, 4),  -- Ancient Crypt requires Iron Shortage
(6, 7, 5),  -- Shadows Over Capital requires Alchemist's Apprentice
(7, 8, 5),  -- Dragon's Awakening requires Alchemist's Apprentice
(8, 8, 6);  -- Dragon's Awakening requires Ancient Crypt

ALTER TABLE quest_prerequisites ALTER COLUMN prerequisite_id RESTART WITH 9;


-- ----------------------------------------------------------------------------
-- 6. SEED PLAYER INVENTORIES
-- ----------------------------------------------------------------------------
INSERT INTO player_inventory (inventory_id, player_id, item_id, quantity, acquired_at)
OVERRIDING SYSTEM VALUE
VALUES
(1, 1, 2, 1, NOW() - INTERVAL '25 days'),  -- Admin: Dragonbone Greatsword
(2, 1, 10, 1, NOW() - INTERVAL '25 days'), -- Admin: Heart of the Void
(3, 2, 1, 1, NOW() - INTERVAL '10 days'),  -- Hero: Iron Longsword
(4, 2, 5, 4, NOW() - INTERVAL '8 days'),   -- Hero: Elixir of Vitality (4x)
(5, 2, 8, 12, NOW() - INTERVAL '6 days'),  -- Hero: Wolf Pelts (12x)
(6, 2, 3, 1, NOW() - INTERVAL '3 days'),   -- Hero: Steel Breastplate
(7, 3, 4, 1, NOW() - INTERVAL '9 days'),   -- Mage: Robes of Nethermancer
(8, 3, 6, 6, NOW() - INTERVAL '7 days'),   -- Mage: Mana Draught (6x)
(9, 3, 7, 1, NOW() - INTERVAL '2 days');   -- Mage: Starfall Phial

ALTER TABLE player_inventory ALTER COLUMN inventory_id RESTART WITH 10;


-- ----------------------------------------------------------------------------
-- 7. SEED PLAYER QUEST PROGRESS
-- ----------------------------------------------------------------------------
INSERT INTO player_quests (player_quest_id, player_id, quest_id, status, started_at, completed_at)
OVERRIDING SYSTEM VALUE
VALUES
-- Hero Quest Progression:
(1, 2, 1, 'completed', NOW() - INTERVAL '12 days', NOW() - INTERVAL '11 days'),
(2, 2, 2, 'completed', NOW() - INTERVAL '10 days', NOW() - INTERVAL '9 days'),
(3, 2, 3, 'completed', NOW() - INTERVAL '8 days', NOW() - INTERVAL '6 days'),
(4, 2, 4, 'active',    NOW() - INTERVAL '4 days', NULL),
(5, 2, 5, 'active',    NOW() - INTERVAL '2 days', NULL),

-- Mage Quest Progression:
(6, 3, 1, 'completed', NOW() - INTERVAL '9 days', NOW() - INTERVAL '8 days'),
(7, 3, 2, 'completed', NOW() - INTERVAL '8 days', NOW() - INTERVAL '7 days'),
(8, 3, 3, 'completed', NOW() - INTERVAL '7 days', NOW() - INTERVAL '6 days'),
(9, 3, 5, 'completed', NOW() - INTERVAL '5 days', NOW() - INTERVAL '3 days'),
(10, 3, 7, 'active',   NOW() - INTERVAL '2 days', NULL);

ALTER TABLE player_quests ALTER COLUMN player_quest_id RESTART WITH 11;


-- ----------------------------------------------------------------------------
-- 8. SEED NPC RELATIONSHIPS (Sentiment Affinity & Interactions)
-- ----------------------------------------------------------------------------
INSERT INTO npc_relationships (relationship_id, player_id, npc_id, affinity_score, interaction_count, last_interaction)
OVERRIDING SYSTEM VALUE
VALUES
(1, 2, 1, 45.00, 8, NOW() - INTERVAL '4 hours'),   -- Hero with Gorim (Friendly)
(2, 2, 2, 60.50, 14, NOW() - INTERVAL '2 hours'),  -- Hero with Elara (Close ally)
(3, 2, 5, 20.00, 4, NOW() - INTERVAL '1 day'),    -- Hero with Captain Roland (Neutral/Respectful)
(4, 3, 3, 85.00, 22, NOW() - INTERVAL '30 mins'),  -- Mage with Archmage Varis (Revered Apprentice)
(5, 3, 4, 35.00, 7, NOW() - INTERVAL '1 day'),    -- Mage with Silas Goldleaf (Good customer)
(6, 3, 2, 40.00, 6, NOW() - INTERVAL '2 days');   -- Mage with Elara (Regular patron)

ALTER TABLE npc_relationships ALTER COLUMN relationship_id RESTART WITH 7;


-- ----------------------------------------------------------------------------
-- 9. SEED INVENTORY TRANSACTIONS (Audit Trail Ledger)
-- ----------------------------------------------------------------------------
INSERT INTO inventory_transactions (transaction_id, player_id, item_id, transaction_type, quantity, gold_amount, description, created_at)
OVERRIDING SYSTEM VALUE
VALUES
(1, 2, 1, 'buy', 1, 50, 'Purchased 1x Iron Longsword from Gorim', NOW() - INTERVAL '10 days'),
(2, 2, 5, 'buy', 5, 125, 'Purchased 5x Elixir of Vitality from Silas', NOW() - INTERVAL '8 days'),
(3, 2, 3, 'quest_reward', 1, 120, 'Reward for completing Quest #3: The Smuggler''s Secret', NOW() - INTERVAL '6 days'),
(4, 3, 4, 'buy', 1, 1800, 'Purchased 1x Robes of the Nethermancer from Archmage Varis', NOW() - INTERVAL '9 days'),
(5, 3, 6, 'buy', 8, 360, 'Purchased 8x Mana Draught from Silas', NOW() - INTERVAL '7 days'),
(6, 3, 7, 'quest_reward', 1, 300, 'Reward for completing Quest #5: The Alchemist''s Apprentice', NOW() - INTERVAL '3 days'),
(7, 2, 5, 'transfer_out', 1, 0, 'Transferred 1x Elixir of Vitality to Player #3 (mage)', NOW() - INTERVAL '1 day'),
(8, 3, 5, 'transfer_in', 1, 0, 'Received 1x Elixir of Vitality from Player #2 (hero)', NOW() - INTERVAL '1 day');

ALTER TABLE inventory_transactions ALTER COLUMN transaction_id RESTART WITH 9;

COMMIT;
