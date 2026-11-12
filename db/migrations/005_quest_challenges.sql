-- ============================================================================
-- Migration 005: Interactive Quest Challenges, Math Puzzles, and CTF Codewords
-- ============================================================================

ALTER TABLE quests ADD COLUMN IF NOT EXISTS challenge_type VARCHAR(100) DEFAULT 'Puzzle';
ALTER TABLE quests ADD COLUMN IF NOT EXISTS challenge_question TEXT;
ALTER TABLE quests ADD COLUMN IF NOT EXISTS challenge_hint TEXT;
ALTER TABLE quests ADD COLUMN IF NOT EXISTS challenge_answer VARCHAR(255);

-- Quest 1: Rats in the Cellar
UPDATE quests SET 
    challenge_type = 'Math Challenge',
    challenge_question = 'Elara counts 3 packs of dire rats in the cellar: East tunnel has 7 rats, West tunnel has 12, and the Central grain storage has double the East tunnel. How many total dire rats must you clear?',
    challenge_hint = 'Calculate: 7 + 12 + (2 * 7)',
    challenge_answer = '33'
WHERE quest_id = 1;

-- Quest 2: Gathering Herbal Flora
UPDATE quests SET 
    challenge_type = 'Apothecary Ratio',
    challenge_question = 'Silas needs moon-orchids for health elixirs. The apothecary ratio is 3 moon-orchids to brew 1 vial of vitality elixir. How many orchids are needed to brew 5 vials?',
    challenge_hint = 'Multiply 3 orchids per vial by 5 vials.',
    challenge_answer = '15'
WHERE quest_id = 2;

-- Quest 3: The Smuggler''s Secret
UPDATE quests SET 
    challenge_type = 'CTF Cipher / NPC Intel',
    challenge_question = 'The canal dock smugglers use an encrypted recognition passphrase. Chat with Elara Ravenshade at the Whispering Crow Inn (ask her about "smuggler secrets" or "dock cipher") to uncover the codeword.',
    challenge_hint = 'Ask Elara in the NPC Dialogue chat about smuggler secrets, or enter SHADOW_CARGO_77.',
    challenge_answer = 'SHADOW_CARGO_77'
WHERE quest_id = 3;

-- Quest 4: The Iron Shortage
UPDATE quests SET 
    challenge_type = 'Dwarven Forge Math',
    challenge_question = 'Master Gorim needs to balance the blast furnace: The recipe requires exactly 3 parts iron ore to 2 parts flux coal. If Gorim has loaded 18 parts iron ore, how many parts flux coal must be added to achieve optimal heat?',
    challenge_hint = '(18 / 3) * 2 = ?',
    challenge_answer = '12'
WHERE quest_id = 4;

-- Quest 5: The Alchemist''s Apprentice
UPDATE quests SET 
    challenge_type = 'Arcane Resonance Math',
    challenge_question = 'Archmage Varis tests your arcane precision: An enchanted mana ward doubles its defensive frequency every hour. If it reaches 64 kHz after 6 hours, what was its starting frequency in kHz at hour 0?',
    challenge_hint = '64 / (2^6) = ?',
    challenge_answer = '1'
WHERE quest_id = 5;

-- Quest 6: The Ancient Crypt
UPDATE quests SET 
    challenge_type = 'Crypt Door Riddle',
    challenge_question = 'The stone door of the Crypt of Karaz bears an ancient runic riddle: "I speak without a voice, I hear without ears. I have no body, but I come alive with the wind. What am I?"',
    challenge_hint = 'A sound that bounces back to you in an empty chamber.',
    challenge_answer = 'echo'
WHERE quest_id = 6;

-- Quest 7: Shadows Over the Capital
UPDATE quests SET 
    challenge_type = 'Cryptographic Logic',
    challenge_question = 'You intercept an encrypted dispatch from the Void Cult containing an authorization code: What is the 4-bit binary result of 1010 XOR 0110?',
    challenge_hint = 'Bitwise XOR comparison: 1^0=1, 0^1=1, 1^1=0, 0^0=0.',
    challenge_answer = '1100'
WHERE quest_id = 7;

-- Quest 8: Dragon''s Awakening
UPDATE quests SET 
    challenge_type = 'Primordial Boss Riddle',
    challenge_question = 'Atop the Mount of Ash, the primordial wyrm breathes embers and challenges your mind before yielding its heart: "Feed me and I live, yet give me water and I die. What am I?"',
    challenge_hint = 'It crackles, burns fuel, and is quenched by water.',
    challenge_answer = 'fire'
WHERE quest_id = 8;
