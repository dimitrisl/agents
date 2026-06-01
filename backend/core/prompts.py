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
6. Is the playstyle_guide correct and consistent with their current level and features?
7. Do they have all required level-up advancements (e.g., level 4 feat/ASI)?
8. Are the character's core identity fields (race, class, subclass, and background) valid for their edition?
- Valid Races/Species for this edition: {allowed_races}
- Valid Classes for this edition: {allowed_classes}
- Valid Backgrounds for this edition: {allowed_backgrounds}
- Valid Subclasses for this class: {allowed_subclasses}

If you find discrepancies, you MUST specify the corrected values in the "corrections" dictionary so they can be applied automatically to the character sheet.
You can correct ANY field in the CharacterSchema by providing it in the "corrections" dictionary:
- "background", "race", "char_class", "subclass"
- "proficiency_bonus", "hp_max", "armor_class", "speed", "passive_perception", "spell_save_dc", "spell_attack_bonus", "initiative_modifier"
- "stats": dictionary of ability scores (STR, DEX, CON, INT, WIS, CHA)
- "prepared_spells": list of strings (fill/update with appropriate spells for their level if currently empty or wrong)
- "features_traits": list of feature objects (name, description, source). If a feature's description is wrong or outdated, provide the corrected list of features.
- "advancements": list of advancement objects (level, type, name, description) representing feats or ASIs. If missing, generate and add them.
- "playstyle_guide": string. If it refers to an outdated level or is incorrect, rewrite it completely to align with the character's current level and features.

Return a JSON object with the following structure exactly:
{{
    "is_valid": true,
    "issues": [],
    "suggestions": [],
    "corrections": {{}}
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
    "weapons": [{{"name": "Warhammer", "attack_bonus": "+5", "damage_dice": "1d8 bludgeoning", "damage_bonus": "+3"}}],
    "equipment": [{{"name": "Chain mail", "equipped": true, "ac_base": 16}}, {{"name": "Shield", "equipped": true, "ac_bonus": 2}}, {{"name": "Backpack", "equipped": false}}],
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
The encounter difficulty level MUST be {difficulty}.

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
            "statblock_summary": "A highly detailed, complete D&D 5e statblock for this creature. Format it beautifully using Markdown. Include Challenge Rating (CR), Speed, Ability Scores, Senses, Languages, Special Traits, and detailed Actions (with attack bonuses, range, and damage)."
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

CRITICAL CLASS & SUBCLASS SEPARATION RULES:
1. "char_class" MUST BE EXACTLY ONE of the base classes (e.g. "Ranger", "Fighter", "Cleric"). Strip out all other words!
2. "subclass" MUST BE the character's subclass/archetype. If the text says "Ranger Horizon Walker", char_class="Ranger" and subclass="Horizon Walker". Do NOT put subclass info in char_class.

Raw PDF Text:
{sheet_text}

Return JSON:
{{
    "char_name": "string",
    "char_class": "string",
    "subclass": "string",
    "char_level": integer,
    "race": "string",
    "background": "string",
    "alignment": "string",
    "armor_class": integer,
    "hp_max": integer,
    "speed": integer,
    "proficiency_bonus": integer,
    "stats": {{"STR": 0, "DEX": 0, "CON": 0, "INT": 0, "WIS": 0, "CHA": 0}},
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
    "weapons": [{{ "name": "...", "attack_bonus": "...", "damage_dice": "...", "damage_bonus": "..." }}],
    "equipment": [],
    "spells": {{ "cantrips": [], "level_1": [] }},
    "features_traits": [{{ "name": "...", "description": "..." }}],
    "languages": [],
    "tool_proficiencies": []
}}
"""


# --- Feat Analysis ---
FEAT_ANALYSIS_PROMPT = """
Analyze the mechanical effects of the D&D {edition} feat: "{feat_name}".

Extract the following technical details as a JSON object:
{{
    "description": "The full, official text of the feat.",
    "stat_bonus": {{"STR": 0, "DEX": 0, "CON": 0, "INT": 0, "WIS": 0, "CHA": 0}},
    "hp_bonus_per_level": 0,
    "hp_bonus_flat": 0,
    "ac_bonus": 0,
    "speed_bonus": 0,
    "has_stat_choice": true,
    "stat_choice_options": ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
}}

Note:
- If the feat gives a +1 to ANY stat of choice, set has_stat_choice to true and list all options.
- If it gives a +1 to a specific stat (e.g. STR), set stat_bonus STR to 1 and has_stat_choice to false.
- For the 'Tough' feat, hp_bonus_per_level should be 2.
"""

RULE_COMPARISON_PROMPT = """
You are the 'Phyrexian Sage', a grand master of D&D evolution.
Your task is to compare the 2014 and 2024 versions of a specific rule, feat, or feature.

Topic: {query}

Provide a structured comparison:
1. **2014 Version**: Briefly explain the legacy mechanic.
2. **2024 Version (5.5e)**: Explain the new mechanic.
3. **Key Changes**: Highlight the most important differences.
4. **Strategic Impact**: How does this change affect character builds or gameplay?

Use a high-contrast markdown table if applicable. Keep the total response under 400 words.
"""

# --- Image Generation ---
PORTRAIT_PROMPT = "High fantasy D&D portrait of a {gender} {race} {char_class}. Background: {background}. Aura: {alignment}. Details: {visual_hooks}. Cinematic lighting, detailed face, digital art masterpiece, high resolution, professional concept art."

MANUAL_CHARACTER_ENRICH_PROMPT = """
You are an expert D&D {edition} Rules Engine.
A player is manually creating a character with the following choices:
- Name: {name}
- Gender: {gender}
- Race/Species: {race}
- Class: {class_name} (Subclass: {subclass})
- Level: {target_level}
- Background: {background}
- Alignment: {alignment}
- Base Stats (before any adjustments): {base_stats}
- Skill Proficiencies: {skill_proficiencies}
- Saving Throw Proficiencies: {saving_throws}
- Spellcasting Ability: {spell_ability}
- Concept: {concept}

Your task is to enrich this character with:
1. Racial features/traits based on their race/species.
2. Background features/traits based on their background.
3. Appropriate class features for a level {target_level} {class_name} (and subclass {subclass}). Include key level progression features like Action Surge, Spellcasting, Cunning Action, etc.
4. Thematic starting weapons and equipment.
5. Standard languages (e.g. Common, plus racial languages).
6. A thematic backstory, personality traits, ideals, bonds, and flaws based on their concept, background, and class.
7. Appropriate spells if they are a spellcaster (cantrips and level 1 spells).

Output strictly a JSON object matching this schema:
{{
    "backstory": "...",
    "features_traits": [
        {{"name": "Feature Name", "description": "Source: Race/Class/Background...", "source": "..."}}
    ],
    "weapons": [
        {{"name": "Longsword", "attack_bonus": "+5", "damage_dice": "1d8", "damage_bonus": "+3"}}
    ],
    "equipment": [
        {{"name": "Scale mail", "equipped": true}},
        {{"name": "Shield", "equipped": true}}
    ],
    "spells": {{
        "cantrips": ["Spell Name"],
        "level_1": ["Spell Name"]
    }},
    "languages": ["Common", "..."],
    "personality_traits": "...",
    "ideals": "...",
    "bonds": "...",
    "flaws": "..."
}}
"""
