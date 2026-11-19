"""LLM service supporting Google Gemini and contextual deterministic Mock providers."""

import json
import logging
import random
import re
from typing import List, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# Fast, generally-available models tried (in order) after the configured one when
# Google reports the primary as busy (HTTP 429/503), slow, or unavailable.
FALLBACK_GEMINI_MODELS = ("gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-flash-lite-latest")
GEMINI_API = "https://generativelanguage.googleapis.com/v1beta/models"


def _gemini_api_key() -> str:
    settings = get_settings()
    key = (settings.gemini_api_key or settings.google_api_key or "").strip()
    if not key or key.startswith("your-") or key.startswith("AIza-placeholder") or key == "mock-key":
        return ""
    return key


def gemini_enabled() -> bool:
    """True when the Gemini provider is selected and a real API key is configured."""
    return get_settings().llm_provider.strip().lower() == "gemini" and bool(_gemini_api_key())


def _gemini_models() -> list:
    primary = get_settings().gemini_model.replace("models/", "").strip()
    models = [primary] if primary else []
    return models + [m for m in FALLBACK_GEMINI_MODELS if m not in models]


def _history_contents(history: Optional[List[dict]], user_message: str) -> List[dict]:
    """Turn recent dialogue ({role: player|npc, text}) plus the new message into Gemini
    multi-turn `contents`, merging consecutive same-role lines and starting with the user."""
    contents: List[dict] = []
    for turn in history or []:
        role = "model" if turn.get("role") == "npc" else "user"
        text = (turn.get("text") or "").strip()
        if not text or (not contents and role == "model"):
            continue
        if contents and contents[-1]["role"] == role:
            contents[-1]["parts"][0]["text"] += "\n" + text
        else:
            contents.append({"role": role, "parts": [{"text": text}]})
    if contents and contents[-1]["role"] == "user":
        contents[-1]["parts"][0]["text"] += "\n" + user_message
    else:
        contents.append({"role": "user", "parts": [{"text": user_message}]})
    return contents


def _gemini_payload(
    model_name: str, system_prompt: str, user_message: str, context: str,
    history: Optional[List[dict]] = None,
) -> dict:
    full_context = system_prompt
    if context:
        full_context += f"\n\n--- WHAT YOU KNOW RIGHT NOW ---\n{context}"
    # Short replies read better in the chat panel and come back much faster.
    full_context += (
        "\n\nRESPONSE LENGTH: 2-4 sentences (under 90 words). At most one short *action* in "
        "asterisks, and only when it adds something. No lists or headings."
    )
    generation_config: dict = {"temperature": 0.9, "topP": 0.95, "maxOutputTokens": 512}
    # Thinking tokens add seconds of latency and count against maxOutputTokens;
    # NPC dialogue doesn't need them.
    if model_name.startswith("gemini-2.5"):
        generation_config["thinkingConfig"] = {"thinkingBudget": 0}
    elif model_name.startswith("gemini-3"):
        generation_config["thinkingConfig"] = {"thinkingLevel": "minimal"}
    return {
        "system_instruction": {"parts": [{"text": full_context}]},
        "contents": _history_contents(history, user_message),
        "generationConfig": generation_config,
    }


def _extract_text(chunk: dict) -> str:
    candidates = chunk.get("candidates") or []
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", []) or []
    # Skip internal "thought" parts; only the visible reply text is returned.
    return "".join(p.get("text", "") for p in parts if not p.get("thought"))


def _generate_gemini_response(
    system_prompt: str, user_message: str, context: str = "", history: Optional[List[dict]] = None
):
    """Non-streaming Gemini call. Returns (reply_text, source) where source is the
    model that answered, or "mock" if every Gemini attempt failed."""
    api_key = _gemini_api_key()
    if not api_key:
        logger.warning("Gemini API key is missing or is a placeholder; using mock replies.")
        return _generate_mock_response(system_prompt, user_message, context), "mock"

    for model_name in _gemini_models():
        # The key is sent in a header (not the URL) so it never appears in logs.
        url = f"{GEMINI_API}/{model_name}:generateContent"
        try:
            with httpx.Client(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
                resp = client.post(
                    url,
                    json=_gemini_payload(model_name, system_prompt, user_message, context, history),
                    headers={"x-goog-api-key": api_key},
                )
        except Exception as exc:
            logger.warning("Gemini (%s) request failed: %s; trying next model.", model_name, exc)
            continue

        if resp.status_code == 200:
            text = _extract_text(resp.json()).strip()
            if text:
                logger.info("Gemini (%s) generated a live NPC reply.", model_name)
                return text, model_name
            logger.warning("Gemini (%s) returned no text; trying next model.", model_name)
        else:
            logger.warning("Gemini (%s) HTTP %d: %s", model_name, resp.status_code, resp.text[:300])

    logger.error("All Gemini models failed. Falling back to mock provider.")
    return _generate_mock_response(system_prompt, user_message, context), "mock"


def stream_response(
    system_prompt: str, user_message: str, context: str = "", history: Optional[List[dict]] = None
):
    """Stream an NPC reply token-by-token.

    Yields ("delta", text) pieces as they arrive, then one ("source", name) naming
    the model that answered ("mock" if Gemini was unavailable). A model that fails
    before producing any text is skipped and the next one is tried.
    """
    if not gemini_enabled():
        yield "delta", _generate_mock_response(system_prompt, user_message, context)
        yield "source", "mock"
        return

    api_key = _gemini_api_key()
    for model_name in _gemini_models():
        url = f"{GEMINI_API}/{model_name}:streamGenerateContent?alt=sse"
        produced = False
        try:
            with httpx.Client(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
                with client.stream(
                    "POST",
                    url,
                    json=_gemini_payload(model_name, system_prompt, user_message, context, history),
                    headers={"x-goog-api-key": api_key},
                ) as resp:
                    if resp.status_code != 200:
                        resp.read()
                        logger.warning("Gemini stream (%s) HTTP %d: %s",
                                       model_name, resp.status_code, resp.text[:300])
                        continue
                    for line in resp.iter_lines():
                        if not line.startswith("data:"):
                            continue
                        try:
                            chunk = json.loads(line[5:].strip())
                        except ValueError:
                            continue
                        text = _extract_text(chunk)
                        if text:
                            produced = True
                            yield "delta", text
        except Exception as exc:
            logger.warning("Gemini stream (%s) failed: %s", model_name, exc)
            if not produced:
                continue
            # Part of the reply is already on screen; finish with what we have.

        if produced:
            logger.info("Gemini (%s) streamed a live NPC reply.", model_name)
            yield "source", model_name
            return
        logger.warning("Gemini stream (%s) returned no text; trying next model.", model_name)

    logger.error("All Gemini models failed while streaming. Falling back to mock provider.")
    yield "delta", _generate_mock_response(system_prompt, user_message, context)
    yield "source", "mock"


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


def generate_response_with_source(
    system_prompt: str, user_message: str, context: str = "", history: Optional[List[dict]] = None
):
    """Generate a reply and report where it came from: a Gemini model name or "mock"."""
    if get_settings().llm_provider.strip().lower() == "gemini":
        return _generate_gemini_response(system_prompt, user_message, context, history)
    return _generate_mock_response(system_prompt, user_message, context), "mock"


def generate_response(system_prompt: str, user_message: str, context: str = "") -> str:
    """Generate an LLM response choosing between Gemini and Mock providers."""
    return generate_response_with_source(system_prompt, user_message, context)[0]
