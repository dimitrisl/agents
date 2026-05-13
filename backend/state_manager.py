import logging
import uuid


logger = logging.getLogger("DnDAssistant.StateManager")


def init_session_state(session_state, force=False):
    """Initializes default Streamlit session state variables."""
    if force or "character_active" not in session_state:
        session_state.character_active = False
    if force or "player_view" not in session_state:
        session_state.player_view = "sheet"
    if force or "char_portrait" not in session_state:
        session_state.char_portrait = None
    if force or "gender" not in session_state:
        session_state.gender = "Male"
    if force or "dnd_edition" not in session_state:
        session_state.dnd_edition = "2014 Edition"
    if force or "needs_validation" not in session_state:
        session_state.needs_validation = False
    if force or "validation_result" not in session_state:
        session_state.validation_result = None

    if force or "char_name" not in session_state:
        session_state.char_id = str(uuid.uuid4())[:8]
        session_state.char_name = "New Hero"
        session_state.char_class = "Paladin"
        session_state.subclass = "Oath of Devotion"
        session_state.char_level = 5
        session_state.race = "Human"
        session_state.gender = "Male"
        session_state.dnd_edition = "2014 Edition"
        session_state.background = "Soldier"
        session_state.alignment = "Lawful Good"
        session_state.backstory = (
            "A valiant paladin who swore an oath of devotion to protect the innocent."
        )
        session_state.armor_class = 18
        session_state.hp_max = 44
        session_state.speed = 30
        session_state.proficiency_bonus = 3
        session_state.stats = {
            "STR": 18,
            "DEX": 12,
            "CON": 15,
            "INT": 10,
            "WIS": 14,
            "CHA": 16,
        }
        session_state.saving_throws = ["WIS", "CHA"]
        session_state.skills = {"Athletics": 7, "Intimidation": 6, "Persuasion": 6}
        session_state.skill_proficiencies = ["Athletics", "Intimidation", "Persuasion"]
        session_state.weapons = [
            {"name": "Longsword", "attack_bonus": "+7", "damage": "1d8+4 slashing"}
        ]
        session_state.equipment = ["Chain mail", "Shield", "Explorer's pack"]
        session_state.features_traits = [
            {
                "name": "Divine Smite",
                "description": "Expend a spell slot to deal radiant damage.",
            }
        ]
        session_state.spells = {
            "level_1": ["Bless", "Cure Wounds", "Shield of Faith"],
            "level_2": ["Find Steed", "Lesser Restoration"],
        }
        session_state.spell_ability = "CHA"
        session_state.spell_save_dc = 14
        session_state.spell_attack_bonus = "+6"

        session_state.hit_dice = "5d10"
        session_state.passive_perception = 12
        session_state.personality_traits = "I'm always polite and respectful."
        session_state.ideals = (
            "Responsibility. I do what I must and obey just authority."
        )
        session_state.bonds = (
            "I'll never forget the crushing defeat my company suffered."
        )
        session_state.flaws = (
            "I have little respect for anyone who is not a proven warrior."
        )

        session_state.build_suggestion = "Click 'Generate New Build Suggestion' to get an AI recommendation based on your current stats!"

        session_state.encounter_result = ""
        session_state.active_campaign = None
        session_state.active_campaign_name = None
        session_state.campaign_notes = ""
        session_state.npc_result = ""
        session_state.session_prep_result = ""
        session_state.party = []
        session_state.temp_forged_char = None
        session_state.advancements = []
        session_state.weapon_masteries = []
        session_state.playstyle_guide = ""
        session_state.initiative_order = []
        session_state.active_turn_index = 0
        session_state.combat_active = False


def get_character_dict(session_state) -> dict:
    """Extracts character data safely from the Streamlit session state into a dictionary."""
    fields = [
        "char_id",
        "char_name",
        "char_class",
        "subclass",
        "char_level",
        "race",
        "gender",
        "background",
        "alignment",
        "backstory",
        "armor_class",
        "hp_max",
        "speed",
        "proficiency_bonus",
        "stats",
        "saving_throws",
        "skills",
        "skill_proficiencies",
        "skill_expertise",
        "weapons",
        "equipment",
        "features_traits",
        "spells",
        "spell_ability",
        "spell_save_dc",
        "spell_attack_bonus",
        "hit_dice",
        "passive_perception",
        "personality_traits",
        "ideals",
        "bonds",
        "flaws",
        "char_portrait",
        "dnd_edition",
        "advancements",
        "weapon_masteries",
        "playstyle_guide",
        "active_campaign",
    ]
    char_data = {}
    for field in fields:
        # Fallback values for critical fields
        default = None
        if field == "stats":
            default = {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}
        elif field == "char_level":
            default = 1
        elif field == "gender":
            default = "Unknown"
        elif field in [
            "saving_throws",
            "weapons",
            "equipment",
            "features_traits",
            "advancements",
            "weapon_masteries",
        ]:
            default = []
        elif field == "skills":
            default = {}
        elif field == "spells":
            default = {}
        elif field == "dnd_edition":
            default = "2014 Edition"

        char_data[field] = getattr(session_state, field, default)

    return char_data


def update_session_from_dict(session_state, data: dict):
    """Updates Streamlit session state variables from a character dictionary."""
    if not data:
        return

    session_state.character_active = True
    session_state.player_view = "sheet"

    # List of all character-related fields to manage
    fields = [
        "char_id",
        "char_name",
        "char_class",
        "subclass",
        "char_level",
        "race",
        "gender",
        "background",
        "alignment",
        "backstory",
        "armor_class",
        "hp_max",
        "speed",
        "proficiency_bonus",
        "stats",
        "saving_throws",
        "skills",
        "skill_proficiencies",
        "skill_expertise",
        "weapons",
        "equipment",
        "features_traits",
        "spells",
        "spell_ability",
        "spell_save_dc",
        "spell_attack_bonus",
        "hit_dice",
        "passive_perception",
        "personality_traits",
        "ideals",
        "bonds",
        "flaws",
        "char_portrait",
        "dnd_edition",
        "advancements",
        "weapon_masteries",
        "playstyle_guide",
        "active_campaign",
    ]

    # RESET all fields first to prevent state bleeding from previous character
    for field in fields:
        default = None
        if field == "stats":
            default = {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}
        elif field == "char_level":
            default = 1
        elif field in [
            "saving_throws",
            "skill_proficiencies",
            "skill_expertise",
            "weapons",
            "equipment",
            "features_traits",
            "advancements",
            "weapon_masteries",
        ]:
            default = []
        elif field in ["skills", "spells"]:
            default = {}

        setattr(session_state, field, default)

    # APPLY new data
    for field in fields:
        if field in data:
            setattr(session_state, field, data[field])
