"""LLM service supporting Google Gemini and contextual deterministic Mock providers."""

import logging
import random
import re
from app.config import get_settings

logger = logging.getLogger(__name__)


def _generate_gemini_response(
    system_prompt: str, user_message: str, context: str = ""
) -> str:
    """Generate a response using the Google Gemini API (via google.generativeai or direct REST)."""
    settings = get_settings()
    api_key = (settings.gemini_api_key or settings.google_api_key or "").strip()

    if not api_key or api_key.startswith("your-") or api_key.startswith("AIza-placeholder") or api_key == "mock-key":
        logger.warning(
            "Gemini API key is missing or is placeholder. Falling back to mock LLM provider."
        )
        return _generate_mock_response(system_prompt, user_message, context)

    full_context = system_prompt
    if context:
        full_context += f"\n\n--- RECALLED MEMORIES / CONTEXT ---\n{context}"

    # 1. Attempt using official google.generativeai SDK if installed
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=full_context,
            generation_config={"temperature": 0.7, "max_output_tokens": 350},
        )
        response = model.generate_content(user_message)
        if response and response.text:
            return response.text.strip()
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("google.generativeai SDK call failed: %s. Falling back to direct REST API.", exc)

    # 2. Attempt using direct Gemini REST API via httpx (built-in, zero external SDK needed)
    try:
        import httpx

        # Standard Google Generative Language REST v1beta endpoint
        model_name = settings.gemini_model.replace("models/", "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

        payload = {
            "system_instruction": {
                "parts": [{"text": full_context}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_message}]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 350
            }
        }

        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"].strip()
            else:
                logger.error("Gemini REST API error (status %d): %s", resp.status_code, resp.text)

    except Exception as exc:
        logger.error("Direct Gemini REST call failed: %s. Falling back to mock provider.", exc)

    return _generate_mock_response(system_prompt, user_message, context)


def _detect_persona(text: str) -> str:
    """Detect NPC archetype from system prompt or name."""
    lower = text.lower()
    if any(k in lower for k in ["gorim", "blacksmith", "smith", "forge", "anvil", "thorin"]):
        return "blacksmith"
    if any(k in lower for k in ["elara", "innkeeper", "tavern", "bartender", "barkeep", "ravenshade"]):
        return "innkeeper"
    if any(k in lower for k in ["varis", "archmage", "mage", "wizard", "sorcerer", "spire"]):
        return "mage"
    if any(k in lower for k in ["silas", "merchant", "goldleaf", "trader", "bazaar", "shopkeeper"]):
        return "merchant"
    if any(k in lower for k in ["roland", "captain", "guard", "watchman", "sentinel", "garrison"]):
        return "guard"
    return "general"


def _extract_context_summary(context: str) -> str:
    """Extract a salient reference only from true retrieved past dialogue memories."""
    if not context or "Recalled Memories from Past Encounters:" not in context:
        return ""
    parts = context.split("Recalled Memories from Past Encounters:")
    if len(parts) < 2:
        return ""
    mem_section = parts[1].strip()
    lines = [line.strip("- * \t") for line in mem_section.splitlines() if line.strip()]
    if lines:
        salient = lines[0]
        salient = re.sub(r"^\[.*?\]:\s*", "", salient)
        salient = re.sub(r'["\']', '', salient).strip()
        if salient and len(salient) > 60:
            salient = salient[:57] + "..."
        return salient
    return ""


def _extract_player_name(context: str) -> str:
    match = re.search(r"Player Character:\s*([A-Za-z0-9_]+)", context)
    return match.group(1) if match else "Adventurer"


def _generate_mock_response(
    system_prompt: str, user_message: str, context: str = ""
) -> str:
    """Generate a rich, persona-aware, contextual response for offline demo and evaluation."""
    persona = _detect_persona(system_prompt + " " + context)
    msg_lower = user_message.lower().strip()
    player_name = _extract_player_name(context)
    memory_ref = _extract_context_summary(context)

    # Clean memory acknowledgment only if a real dialogue memory exists
    ack = ""
    if memory_ref:
        ack = f"I still remember when you said, '{memory_ref}'. "

    # -------------------------------------------------------------------------
    # 1. GORIM IRONBREAKER (Dwarven Master Blacksmith)
    # -------------------------------------------------------------------------
    if persona == "blacksmith":
        if any(w in msg_lower for w in ["ore", "shortage", "furnace", "flux", "coal", "ratio"]):
            return (
                f"{ack}Aye! The dwarven blast furnace ratio is strict: exactly 3 parts iron ore to 2 parts flux coal. "
                f"If you've got 18 parts iron ore, you need (18 / 3) * 2 = 12 parts flux coal to hit peak forging heat without cracking the crucible!"
            )
        if any(w in msg_lower for w in ["rumour", "rumor", "news", "hear", "word"]):
            return (
                f"{ack}Rumors? Aye, plenty. The caravans from the northern mines are a week overdue. "
                f"Word is that goblins or mountain bandits set an ambush at High Pass. If they cut off our "
                f"iron ore shipments, half the forges in the district will go cold."
            )
        if any(w in msg_lower for w in ["about you", "who are you", "yourself", "about u"]):
            return (
                f"{ack}Name's Gorim Ironbreaker. I've pounded anvil steel for seventy winters. "
                f"My clan forged the vanguard shields for the High King himself. I don't care much for "
                f"court manners or cheap flattery—bring me honest ore and good coin, and you'll wield the finest blade in the realm."
            )
        if any(w in msg_lower for w in ["weapon", "sword", "blade", "axe", "hammer", "dagger"]):
            return (
                f"{ack}Now you're talking proper business! I have high-carbon Iron Longswords folded sixteen times, "
                f"and if you've got the coin and glory, I can tell you tales of the legendary Dragonbone Greatsword. "
                f"Check my shop stock in the Market & Vault!"
            )
        if any(w in msg_lower for w in ["armor", "shield", "protect", "plate", "breastplate"]):
            return (
                f"{ack}Good armor is the only reason fools like you survive past their first goblin den. "
                f"I've got reinforced Steel Breastplates tempered in wyrm-oil. Solid enough to turn aside crossbow bolts."
            )
        if any(w in msg_lower for w in ["quest", "job", "work", "task", "help"]):
            return (
                f"{ack}If you're itching for work, check with Captain Roland at the watchtower, or find out what happened "
                f"to the missing ore shipment. You bring me 10 pieces of pristine iron ore, and I'll temper a custom blade for you."
            )
        if any(w in msg_lower for w in ["price", "cost", "gold", "buy", "sell"]):
            return (
                f"{ack}My prices are fair, {player_name}. Quality craftsmanship doesn't haggle with cheapskates. "
                f"Head over to the Market tab to inspect the current catalog."
            )
        if any(w in msg_lower for w in ["hello", "hi", "greetings", "hey"]):
            return (
                f"{ack}Greetings, {player_name}. Watch your elbows around the forge coals. What brings you to the Obsidian Forge today?"
            )
        fallbacks = [
            f"{ack}The anvil rings true today, {player_name}. Tell me what gear you need hammer-shaped, or step aside so I can finish this quench.",
            f"{ack}Steel never lies, traveler. If you have questions about weapons or armor, ask away. Otherwise, the forge demands my eye.",
            f"{ack}Every strike of my hammer tempers the metal. Speak plainly, {player_name}—what's on your mind?",
        ]
        return random.choice(fallbacks)

    # -------------------------------------------------------------------------
    # 2. ELARA RAVENSHADE (Innkeeper & Former Rogue)
    # -------------------------------------------------------------------------
    elif persona == "innkeeper":
        if any(w in msg_lower for w in ["smuggler", "cipher", "passphrase", "dock", "codeword", "vault"]):
            return (
                f"{ack}*looks around cautiously and leans across the counter* "
                f"Keep your voice down, {player_name}... The canal smugglers use the recognition cipher "
                f"'SHADOW_CARGO_77'. Use it at the dock vault gates, and don't tell anyone you heard it from me."
            )
        if any(w in msg_lower for w in ["rumour", "rumor", "news", "secret", "hear", "word"]):
            return (
                f"{ack}*leans in and whispers* You want rumors? You came to the right hearth. "
                f"A hooded scholar arrived two nights ago asking about necromancer crypts beneath the barrows. "
                f"And Silas Goldleaf seems very nervous about an exotic smuggling ring being investigated by the guards."
            )
        if any(w in msg_lower for w in ["about you", "who are you", "yourself", "about u"]):
            return (
                f"{ack}I run the Whispering Crow Inn, darling. In my younger days, I danced across the rooftops with "
                f"the Shadow Guild. Now I find it much safer—and vastly more lucrative—to pour spiced mead and listen to loose tongues."
            )
        if any(w in msg_lower for w in ["drink", "ale", "beer", "wine", "food", "mead"]):
            return (
                f"{ack}Coming right up! We have honeyed mead from the western apiaries and fresh venison stew simmering. "
                f"Ten copper coins for the drink, and the tavern gossip is on the house."
            )
        if any(w in msg_lower for w in ["room", "sleep", "bed", "rest", "night"]):
            return (
                f"{ack}A clean bed and warm hearth await upstairs. No thieves or cutpurses under my roof—I made sure "
                f"the local guild knows this tavern is off-limits."
            )
        if any(w in msg_lower for w in ["quest", "job", "work", "task", "help"]):
            return (
                f"{ack}Looking for adventure, {player_name}? Take a look at the Quest Log. 'The Smuggler's Secret' "
                f"might be right up your alley if you have quiet boots and sharp eyes."
            )
        if any(w in msg_lower for w in ["hello", "hi", "greetings", "hey"]):
            return (
                f"{ack}Welcome to the Whispering Crow, {player_name}! Pull up a chair by the hearth and shake off the road dust."
            )
        fallbacks = [
            f"{ack}In a place like this, everyone has a story—and a price. What brings you to my tavern today, {player_name}?",
            f"{ack}Keep your ears open and your daggers sharp, traveler. What else would you like to know?",
            f"{ack}Secrets are like fine wine—they get better with time. Tell me what you're searching for.",
        ]
        return random.choice(fallbacks)

    # -------------------------------------------------------------------------
    # 3. ARCHMAGE VARIS (Spire of Whispers)
    # -------------------------------------------------------------------------
    elif persona == "mage":
        if any(w in msg_lower for w in ["ward", "frequency", "alchemist", "khz", "resonance"]):
            return (
                f"{ack}A resonant protective mana ward doubles its oscillation frequency exponentially every hour. "
                f"If the measurement is 64 kHz after 6 hours, dividing by 2^6 (which is 64) reveals its initial baseline was exactly 1 kHz."
            )
        if any(w in msg_lower for w in ["rumour", "rumor", "news", "anomaly", "rift"]):
            return (
                f"{ack}The ley lines are vibrating with unnatural resonance. A planar rift has opened near the "
                f"Forgotten Ruins, leaking void essence into our atmosphere. If the Heart of the Void is not secured, "
                f"the dimensional tear will widen."
            )
        if any(w in msg_lower for w in ["about you", "who are you", "yourself", "about u"]):
            return (
                f"{ack}I am Archmage Varis, Keeper of the Spire of Whispers. For three centuries I have observed "
                f"the celestial weave of mana and chronicled the arcane histories of this continent."
            )
        if any(w in msg_lower for w in ["spell", "magic", "arcane", "scroll", "mana"]):
            return (
                f"{ack}Mana is not a weapon to be swung recklessly; it is mathematics intertwined with willpower. "
                f"If your arcane reserves run dry, drink a distilled Mana Draught or study the ancient grimoires."
            )
        if any(w in msg_lower for w in ["quest", "job", "task", "help"]):
            return (
                f"{ack}I have tasks suitable for an inquisitive mind. The 'Planar Rift Anomaly' quest requires an "
                f"adventurer brave enough to probe the void energies. Check your Quest Log for prerequisites."
            )
        if any(w in msg_lower for w in ["hello", "hi", "greetings"]):
            return (
                f"{ack}Greetings, disciple. The astral currents carried your footsteps to my study. What esoteric knowledge do you seek?"
            )
        fallbacks = [
            f"{ack}Reality is far more pliable than the uninitiated realize, {player_name}. What queries bring you to the Spire?",
            f"{ack}The constellations shift constantly. Speak of your purpose, and let us see what the arcane reveals.",
        ]
        return random.choice(fallbacks)

    # -------------------------------------------------------------------------
    # 4. SILAS GOLDLEAF (Bazaar Merchant)
    # -------------------------------------------------------------------------
    elif persona == "merchant":
        if any(w in msg_lower for w in ["rumour", "rumor", "news", "deal"]):
            return (
                f"{ack}Between you and me? The Trade Guild is predicting a severe shortage of moonflower herbs. "
                f"Potion prices will skyrocket next week! Best stock up on Elixirs of Vitality while my vault is full."
            )
        if any(w in msg_lower for w in ["about you", "who are you", "yourself", "about u"]):
            return (
                f"{ack}Silas Goldleaf at your service! Purveyor of the rarest artifacts, potions, and curiosities "
                f"from the four corners of the globe. If it has value, I can buy it, sell it, or appraise it!"
            )
        if any(w in msg_lower for w in ["buy", "sell", "trade", "price", "gold", "shop"]):
            return (
                f"{ack}Ah, music to my ears! I buy high and sell fair. Check the Market & Vault tab right now—"
                f"potions, rare wolf pelts, and precious relics await your coin purse!"
            )
        if any(w in msg_lower for w in ["hello", "hi", "greetings"]):
            return (
                f"{ack}A delightful day to you, honored customer! Step closer—see what treasures Silas has procured today!"
            )
        fallbacks = [
            f"{ack}Every coin tells an adventure, {player_name}! Looking to invest in health potions or unload monster trophies?",
            f"{ack}A satisfied customer is the best business strategy. How can Silas serve your expedition today?",
        ]
        return random.choice(fallbacks)

    # -------------------------------------------------------------------------
    # 5. CAPTAIN ROLAND (Garrison Watchtower)
    # -------------------------------------------------------------------------
    elif persona == "guard":
        if any(w in msg_lower for w in ["rumour", "rumor", "news", "threat", "danger"]):
            return (
                f"{ack}Keep your voice down. We intercepted goblin scouts near the lower farmland this morning. "
                f"I've doubled the perimeter sentries, but we lack capable skirmishers to clear out their vanguard."
            )
        if any(w in msg_lower for w in ["about you", "who are you", "yourself", "about u"]):
            return (
                f"{ack}Captain Roland of the City Guard. My duty is simple: preserve order, enforce the King's peace, "
                f"and ensure the citizens sleep safely at night. Obey the law and we will get along fine."
            )
        if any(w in msg_lower for w in ["quest", "job", "bounty", "work", "help"]):
            return (
                f"{ack}The Garrison is issuing official bounties. Check your Quest Log for 'The Goblin Vanguard'. "
                f"Bring back proof of eliminated raiders, and the crown will reward you with cold gold and experience."
            )
        if any(w in msg_lower for w in ["hello", "hi", "greetings"]):
            return (
                f"{ack}Stand easy, {player_name}. State your business with the Garrison Watch."
            )
        fallbacks = [
            f"{ack}Remain vigilant in these streets, citizen. What matters do you wish to report?",
            f"{ack}The Guard protects all who walk in the light. How can the garrison assist you today?",
        ]
        return random.choice(fallbacks)

    # -------------------------------------------------------------------------
    # GENERAL FALLBACK
    # -------------------------------------------------------------------------
    if any(w in msg_lower for w in ["rumour", "rumor", "news"]):
        return f"{ack}Whispers speak of ancient vaults reopening and merchant caravans ambushed on the western road."
    if any(w in msg_lower for w in ["about you", "who are you", "yourself", "about u"]):
        return f"{ack}I am a resident of this realm, observing the rise and fall of heroes and empires."
    if any(w in msg_lower for w in ["hello", "hi", "greetings"]):
        return f"{ack}Greetings, {player_name}. What purpose brings you to speak with me today?"

    return (
        f"{ack}I hear you clearly, {player_name}. Your words carry weight in these lands—tell me more about what you intend to do."
    )


def generate_response(
    system_prompt: str, user_message: str, context: str = ""
) -> str:
    """Generate an LLM response choosing between Gemini and Mock providers."""
    settings = get_settings()
    provider = settings.llm_provider.strip().lower()

    if provider == "gemini":
        return _generate_gemini_response(system_prompt, user_message, context)
    else:
        return _generate_mock_response(system_prompt, user_message, context)
