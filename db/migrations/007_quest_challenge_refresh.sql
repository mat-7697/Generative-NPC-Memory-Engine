-- ============================================================================
-- Migration 007: Clear, self-contained quest challenges with useful hints.
-- Every puzzle can be solved from the question text alone; the hint nudges the
-- player toward the method without just printing the answer.
-- challenge_answer may list several accepted answers separated by "|".
-- Answers are compared case-insensitively, ignoring spaces/punctuation and a
-- leading "the/a/an" (see _normalize_answer in backend/app/routers/quests.py).
-- ============================================================================

UPDATE quests SET
    challenge_type = 'Arithmetic',
    challenge_question = 'Elara found 3 rat nests in the inn cellar. Each nest holds 4 dire rats, and 2 alpha rats roam freely between the nests. How many rats must you clear in total?',
    challenge_hint = 'First count the rats inside the nests (3 nests x 4 rats), then add the alphas that live outside them.',
    challenge_answer = '14'
WHERE quest_id = 1;

UPDATE quests SET
    challenge_type = 'Riddle',
    challenge_question = 'Silas needs a rare flower for his healing elixirs: "I open my petals only under moonlight and close them at dawn. My name joins the light of the night sky with an exotic bloom." What flower am I?',
    challenge_hint = 'Two words joined together: the thing that shines at night + a tropical flower often sold in pots (starts with "orch...").',
    challenge_answer = 'moon-orchid|moon orchids'
WHERE quest_id = 2;

UPDATE quests SET
    challenge_type = 'Reverse Cipher',
    challenge_question = 'You intercept a note from the dock smugglers. To hide their password they wrote it backwards: "ROHCNA". What is the real password?',
    challenge_hint = 'Read the letters from right to left. It is the heavy iron object a ship drops to stay in place.',
    challenge_answer = 'ANCHOR'
WHERE quest_id = 3;

UPDATE quests SET
    challenge_type = 'Caesar Cipher',
    challenge_question = 'Master Gorim sent his supply order in code, shifting every letter ONE step forward in the alphabet (A becomes B, B becomes C...). The order reads: "JSPO PSF". What does the forge need?',
    challenge_hint = 'Shift each letter one step back: J -> I, S -> R, P -> O, O -> N ... The answer is two words.',
    challenge_answer = 'IRON ORE'
WHERE quest_id = 4;

UPDATE quests SET
    challenge_type = 'Ratio Puzzle',
    challenge_question = 'The apprentice''s recipe: 2 moon-orchids + 3 mana draughts = 5 warding crystals. You have 6 moon-orchids and 9 mana draughts. How many warding crystals can you brew?',
    challenge_hint = 'Compare your ingredients to the recipe: 6 is 3 times 2, and 9 is 3 times 3. So multiply the output by the same amount.',
    challenge_answer = '15'
WHERE quest_id = 5;

UPDATE quests SET
    challenge_type = 'Riddle',
    challenge_question = 'Words carved on the crypt door of Karaz: "I speak without a mouth and hear without ears. I have no body, yet in these empty halls I answer every call." Speak the answer to open the door.',
    challenge_hint = 'Shout into an empty cave or hall and listen to what comes back to you.',
    challenge_answer = 'echo'
WHERE quest_id = 6;

UPDATE quests SET
    challenge_type = 'Number Sequence',
    challenge_question = 'A Void Cult lockbox has a number dial. Scratched beside it is a pattern with the last number missing: 3, 6, 12, 24, ?. What number opens the lockbox?',
    challenge_hint = 'Look at how each number relates to the one before it: every step doubles the previous number.',
    challenge_answer = '48'
WHERE quest_id = 7;

UPDATE quests SET
    challenge_type = 'Riddle',
    challenge_question = 'Atop the Mount of Ash, the ancient wyrm speaks: "Feed me and I grow, give me drink and I die. I am the breath of every dragon." What am I?',
    challenge_hint = 'It crackles, needs fuel like wood to grow, and water puts it out.',
    challenge_answer = 'fire|flame|flames'
WHERE quest_id = 8;
