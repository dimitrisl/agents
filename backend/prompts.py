# Centralized prompt templates for the Phyrexian Forge AI services

# --- Rules & Validation ---
RULES_ORACLE_PROMPT = """
You are the 'Phyrexian Oracle', an expert on Dungeons & Dragons {edition} rules.
Answer the following question clearly and concisely.
The answer MUST BE no more than 5 sentences long.
If the rule changed between 2014 and 2024, and the user is asking about {edition}, make sure to provide the version-accurate answer.

Question: {query}

Answer (be helpful, use markdown for formatting):
"""

BUILD_VALIDATION_PROMPT = """
You are an expert Dungeon Master and Rules Arbiter for Dungeons & Dragons.
Your task is to validate a character sheet to ensure it complies with the official rules.

Character Data:
{char_json}

Validate the following aspects based on their edition ({edition}):
1. Are the Ability Scores possible? (e.g., standard array/point buy + racial bonuses, no score above 20 unless a specific feature allows it).
2. Is the Max HP reasonable for their class, level, and CON modifier?
3. Is the Proficiency Bonus correct for their level?
4. Do they have too many or too few features/traits for their level and class?
5. Are their spell slots correct for their class and level?

Return a JSON object with the following structure exactly:
{{
    "is_valid": true,
    "issues": [],
    "suggestions": []
}}
"""

# --- Character Forge ---
CHARACTER_FORGE_PROMPT = """
Create a fully fleshed out level {target_level} D&D {edition} character.
{name_instruction}
Gender: {gender}
Race: {race}
Class: {class_name}
Background: {background}
Flavor/Concept: {concept}
Subclass: {subclass}
Alignment: {alignment}

STRICT RULES:
1. Race/Species MUST be one of: {current_races}
2. Class MUST be one of: {current_classes}
3. Background MUST be one of: {current_backgrounds}

{stats_instruction}

Calculate their HP, AC, Proficiency Bonus, and choose appropriate skills, weapons, equipment, features/traits, and spells (if applicable) for a level {target_level} character.
If the level is 4 or higher (or 1 if 2024 edition), explicitly list their Feats and Ability Score Improvements (ASI) in the 'advancements' field.

Output the character strictly as a JSON object with exactly the following schema:
{{
    "char_name": "Name of the character",
    "gender": "...",
    "char_class": "...",
    "subclass": "...",
    "char_level": {target_level},
    "race": "...",
    "background": "...",
    "alignment": "...",
    "backstory": "...",
    "armor_class": 16,
    "hp_max": 45,
    "speed": 30,
    "proficiency_bonus": 3,
    "stats": {{
        "STR": 15, "DEX": 10, "CON": 14, "INT": 8, "WIS": 12, "CHA": 10
    }},
    "saving_throws": ["STR", "CON"],
    "skills": {{"Athletics": 5, "Intimidation": 2}},
    "skill_proficiencies": ["Athletics", "Intimidation"],
    "skill_expertise": [],
    "weapon_masteries": ["Slow", "Topple"],
    "weapons": [{{"name": "Warhammer", "attack_bonus": "+5", "damage": "1d8+3 bludgeoning"}}],
    "equipment": [{"name": "Chain mail", "equipped": true, "ac_base": 16}, {"name": "Shield", "equipped": true, "ac_bonus": 2}, {"name": "Backpack", "equipped": false}],
    "features_traits": [{{"name": "Action Surge", "description": "Push yourself..."}}],
    "spells": {{"cantrips": ["Fire Bolt"], "level_1": ["Shield"]}},
    "spell_ability": "INT",
    "spell_save_dc": 15,
    "spell_attack_bonus": "+7",
    "hit_dice": "1d10",
    "passive_perception": 12,
    "advancements": [{{"level": 4, "type": "ASI", "name": "Ability Score Improvement", "description": "Increase INT by 2"}}],
    "personality_traits": "...",
    "ideals": "...",
    "bonds": "...",
    "flaws": "...",
    "languages": ["Common", "Elvish"],
    "tool_proficiencies": ["Thieves' Tools", "Lute"]
}}
"""


PLAYSTYLE_GUIDE_PROMPT = """
Create a detailed D&D {edition} Playstyle Guide for the following character:
Name: {name}
Class: {class_name} (Subclass: {subclass})
Level: {level}
Race/Species: {race}
Background: {background}
Stats: {stats}
Features: {features}

The guide should include:
1. **Combat Strategy**: How to use their actions, bonus actions, and features optimally.
2. **Roleplay Tips**: How to portray their personality and background in the world.
3. **Key Synergies**: How their features work together.

Use beautiful markdown formatting with headings, bullet points, and emphasis.
"""

LEVEL_UP_ANALYSIS_PROMPT = """
Act as a D&D {edition} Rules Expert and Tactical Optimizer.
Analyze the following character and determine EXACTLY what changes when they level up from Level {current_level} to Level {target_level}.

Character Info:
- Class: {char_class}
- Subclass: {subclass}
- Race/Species: {race}
- Stats: {stats}

Return a JSON object with the following structure:
{{
    "automatic_changes": [
        {{"name": "Feature Name", "description": "..."}}
    ],
    "hp_increase": 8,
    "new_total_hp": 42,
    "choices_required": [
        {{
            "type": "subclass|feat|spell|infusion|invocation|other",
            "label": "Give a clear title for this choice",
            "options": ["Option 1", "Option 2"],
            "ai_recommendation": "Explain WHY this is the best choice for this specific build."
        }}
    ],
    "updated_proficiency_bonus": 3,
    "updated_spell_slots": {{ "level_1": 4 }},
    "suggestions": [
        "A tactical tip for playing this character at the new level."
    ]
}}

STRICT CLASS RULES:
- ARTIFICER: If Level 2, 6, 10, 14, they gain NEW Infusion options. List them in choices or features.
- WARLOCK: If Level 2, 5, 7, 9, 12, 15, 18, they gain NEW Eldritch Invocations.
- FIGHTER: Gain extra ASI/Feats at levels 4, 6, 8, 12, 14, 16, 19.
- SPELLCASTERS: If they learn new spells (e.g. Sorcerer, Bard, Ranger), include them in choices_required.

Ruleset specific notes:
- If 2024 Edition, remember that Subclasses are now ALWAYS chosen at Level 3.
- If Level 4, 8, 12, 16, 19, there is always a Choice (Feat or ASI).
"""

# --- DM Tools ---
RANDOM_ENCOUNTER_PROMPT = """
Generate a flavorful random encounter for a D&D {edition} party of {party_size} level {avg_level} characters.
The setting is {location}.

You must return a JSON object with the following structure:
{{
    "encounter_text": "Markdown formatted description...",
    "monsters": [
        {{
            "name": "...",
            "hp": 45,
            "ac": 15,
            "dex": 12,
            "quantity": 3,
            "statblock_summary": "..."
        }}
    ]
}}
"""

RIDDLE_PROMPT = """
You are a master of puzzles and enigmas in D&D {edition}.
Generate a clever riddle that fits perfectly within the environment: {location}.

The response should be formatted in markdown and include:
1. **The Riddle**: A short, poetic, or cryptic puzzle.
2. **Hint**: A subtle clue for the DM to give if the players are stuck.
3. **The Answer**: The solution to the riddle.
"""

NPC_PROMPT = """
Create a D&D {edition} NPC based on: "{npc_concept}".
Include their Name, Race/Species, Appearance, Personality Trait, and a secret they are hiding.
Format nicely with Markdown. Keep it brief and punchy.
"""

SESSION_PREP_PROMPT = """
I am a Dungeon Master preparing for my next D&D 5e session.
Campaign Notes: {campaign_notes}
Party Composition: {party_info}

Based on the notes and the party, generate 3 creative plot hooks, twists, or developments for the next session.
Format with markdown, headings for each hook. Total under 250 words.
"""

# --- Parsing ---
PDF_PARSING_STEP1_PROMPT = """
Act as an expert D&D {edition} parser.
Extract the CORE identity and statistics from the character sheet text.
Handle context for non-English labels (e.g. Italian 'Forza' -> STR).

Raw PDF Text:
{sheet_text}

Return JSON:
{{
    "char_name": "string",
    "char_class": "string",
    "char_level": integer,
    "race": "string",
    "background": "string",
    "alignment": "string",
    "armor_class": integer,
    "hp_max": integer,
    "speed": integer,
    "proficiency_bonus": integer,
    "stats": {{"STR": 0, "DEX": 0, ...}},
    "saving_throws": [],
    "skills": {{"Name": 0}},
    "skill_proficiencies": [],
    "skill_expertise": [],
    "languages": [],
    "tool_proficiencies": []
}}
"""

PDF_PARSING_STEP2_PROMPT = """
Act as an expert D&D {edition} parser.
Context from Step 1: {core_json}

Extract Combat, Equipment, Spells, Features & Lore.
Raw PDF Text:
{sheet_text}

Return JSON:
{{
    "backstory": "...",
    "personality_traits": "...",
    "ideals": "...",
    "bonds": "...",
    "flaws": "...",
    "weapons": [{{ "name": "...", "attack_bonus": "...", "damage": "..." }}],
    "equipment": [],
    "spells": {{ "cantrips": [], "level_1": [] }},
    "features_traits": [{{ "name": "...", "description": "..." }}],
    "languages": [],
    "tool_proficiencies": []
}}
"""
