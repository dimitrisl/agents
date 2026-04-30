# Shared constants for the D&D AI Assistant

EDITION_2014 = "2014 Edition"
EDITION_2024 = "2024 Revision (5.5e)"
EDITIONS = [EDITION_2014, EDITION_2024]

GENDERS = ["Male", "Female"]

ALIGNMENTS = [
    "Lawful Good",
    "Neutral Good",
    "Chaotic Good",
    "Lawful Neutral",
    "True Neutral",
    "Chaotic Neutral",
    "Lawful Evil",
    "Neutral Evil",
    "Chaotic Evil",
]

# ==========================================
# 2014 Ruleset (5e)
# ==========================================
RACES_2014 = [
    "Human",
    "Elf",
    "Dwarf",
    "Halfling",
    "Dragonborn",
    "Tiefling",
    "Half-Orc",
    "Gnome",
    "Half-Elf",
]

CLASSES_2014 = [
    "Barbarian",
    "Bard",
    "Cleric",
    "Druid",
    "Fighter",
    "Monk",
    "Paladin",
    "Ranger",
    "Rogue",
    "Sorcerer",
    "Warlock",
    "Wizard",
]

BACKGROUNDS_2014 = [
    "Acolyte",
    "Charlatan",
    "Criminal",
    "Entertainer",
    "Folk Hero",
    "Guild Artisan",
    "Hermit",
    "Noble",
    "Outlander",
    "Sage",
    "Sailor",
    "Soldier",
    "Urchin",
]

SUBCLASSES_2014 = {
    "Barbarian": ["Path of the Berserker", "Path of the Totem Warrior"],
    "Bard": ["College of Lore", "College of Valor"],
    "Cleric": [
        "Knowledge Domain",
        "Life Domain",
        "Light Domain",
        "Nature Domain",
        "Tempest Domain",
        "Trickery Domain",
        "War Domain",
    ],
    "Druid": ["Circle of the Land", "Circle of the Moon"],
    "Fighter": ["Champion", "Battle Master", "Eldritch Knight"],
    "Monk": ["Way of the Open Hand", "Way of Shadow", "Way of the Four Elements"],
    "Paladin": ["Oath of Devotion", "Oath of the Ancients", "Oath of Vengeance"],
    "Ranger": ["Hunter", "Beast Master"],
    "Rogue": ["Thief", "Assassin", "Arcane Trickster"],
    "Sorcerer": ["Draconic Bloodline", "Wild Magic"],
    "Warlock": ["The Archfey", "The Fiend", "The Great Old One"],
    "Wizard": [
        "School of Abjuration",
        "School of Conjuration",
        "School of Divination",
        "School of Enchantment",
        "School of Evocation",
        "School of Illusion",
        "School of Necromancy",
        "School of Transmutation",
    ],
}

# ==========================================
# 2024 Ruleset (5.5e)
# ==========================================
SPECIES_2024 = [
    "Aasimar",
    "Dragonborn",
    "Dwarf",
    "Elf",
    "Gnome",
    "Goliath",
    "Halfling",
    "Human",
    "Orc",
    "Tiefling",
]

CLASSES_2024 = CLASSES_2014  # Same core classes

BACKGROUNDS_2024 = [
    "Acolyte",
    "Artisan",
    "Charlatan",
    "Criminal",
    "Entertainer",
    "Farmer",
    "Guard",
    "Guide",
    "Hermit",
    "Merchant",
    "Noble",
    "Sage",
    "Sailor",
    "Scribe",
    "Soldier",
    "Wayfarer",
]

SUBCLASSES_2024 = {
    "Barbarian": [
        "Path of the Berserker",
        "Path of the Wild Heart",
        "Path of the World Tree",
        "Path of the Zealot",
    ],
    "Bard": [
        "College of Dance",
        "College of Glamour",
        "College of Lore",
        "College of Valor",
    ],
    "Cleric": ["Life Domain", "Light Domain", "Trickery Domain", "War Domain"],
    "Druid": [
        "Circle of the Land",
        "Circle of the Moon",
        "Circle of the Sea",
        "Circle of the Stars",
    ],
    "Fighter": ["Battle Master", "Champion", "Eldritch Knight", "Psi Warrior"],
    "Monk": [
        "Warrior of Mercy",
        "Warrior of Shadow",
        "Warrior of the Elements",
        "Warrior of the Open Hand",
    ],
    "Paladin": [
        "Oath of Devotion",
        "Oath of Glory",
        "Oath of the Ancients",
        "Oath of Vengeance",
    ],
    "Ranger": ["Beast Master", "Fey Wanderer", "Gloom Stalker", "Hunter"],
    "Rogue": ["Arcane Trickster", "Assassin", "Soulknife", "Thief"],
    "Sorcerer": [
        "Aberrant Sorcery",
        "Clockwork Sorcery",
        "Draconic Sorcery",
        "Wild Magic",
    ],
    "Warlock": [
        "Archfey Patron",
        "Celestial Patron",
        "Fiend Patron",
        "Great Old One Patron",
    ],
    "Wizard": ["Abjurer", "Diviner", "Evoker", "Illusionist"],
}

WEAPON_MASTERIES_2024 = [
    "Cleave",
    "Graze",
    "Nick",
    "Push",
    "Sap",
    "Slow",
    "Topple",
    "Vex",
]

# PDF Positioning
PDF_PORTRAIT_X = 45
PDF_PORTRAIT_Y = 450
PDF_PORTRAIT_WIDTH = 175
PDF_PORTRAIT_HEIGHT = 180
