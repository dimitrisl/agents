"""Canonical D&D 2024 Revision (5.5e) subclass progression features across all 13 classes."""

SUBCLASS_FEATURES_DETAILS_2024: dict[tuple[str, str, int], dict[str, str]] = {
    # ==========================================
    # Fighter (3, 7, 10, 15, 18)
    # ==========================================
    ("Fighter", "Champion", 3): {
        "name": "Improved Critical & Remarkable Athlete (Champion)",
        "description": "Critical hit on a roll of 19 or 20. In addition, thanks to athletic prowess, you have Advantage on Initiative rolls and Strength (Athletics) checks; running jump distance increases by STR modifier in feet.",
    },
    ("Fighter", "Champion", 7): {
        "name": "Additional Fighting Style (Champion)",
        "description": "Choose a second option from the Fighting Style class feature.",
    },
    ("Fighter", "Champion", 10): {
        "name": "Heroic Warrior (Champion)",
        "description": "Whenever you start your turn in combat without Heroic Inspiration, you can give yourself Heroic Inspiration.",
    },
    ("Fighter", "Champion", 15): {
        "name": "Superior Critical (Champion)",
        "description": "Your weapon attacks score a critical hit on a roll of 18-20.",
    },
    ("Fighter", "Champion", 18): {
        "name": "Survivor (Champion)",
        "description": "At the start of each of your turns, you regain 5 + CON modifier HP if you have no more than half your HP left, and have Advantage on Death Saving Throws.",
    },
    ("Fighter", "Battle Master", 3): {
        "name": "Combat Superiority & Student of War (Battle Master)",
        "description": "Gain 3 maneuvers and 4 Superiority Dice (d8), plus proficiency in one Artisan's Tool and one skill available to Fighters.",
    },
    ("Fighter", "Battle Master", 7): {
        "name": "Know Your Enemy (Battle Master)",
        "description": "As a Bonus Action, learn whether a creature within 30 feet has Immunities, Resistances, or Vulnerabilities and what they are (recharges on Long Rest or by spending a Superiority Die).",
    },
    ("Fighter", "Battle Master", 10): {
        "name": "Improved Combat Superiority (Battle Master)",
        "description": "Your Superiority Dice increase to d10s.",
    },
    ("Fighter", "Battle Master", 15): {
        "name": "Relentless (Battle Master)",
        "description": "Once per turn when you use a maneuver, you can roll 1d8 and use that roll instead of expending a Superiority Die.",
    },
    ("Fighter", "Battle Master", 18): {
        "name": "Ultimate Combat Superiority (Battle Master)",
        "description": "Your Superiority Dice increase to d12s.",
    },
    ("Fighter", "Eldritch Knight", 3): {
        "name": "Spellcasting & War Bond (Eldritch Knight)",
        "description": "Augment martial prowess with Wizard spells (INT) and bond with up to two weapons so you cannot be disarmed and can summon them as a Bonus Action.",
    },
    ("Fighter", "Eldritch Knight", 7): {
        "name": "War Magic (Eldritch Knight)",
        "description": "When you take the Attack action on your turn, you can replace one of your attacks with a casting of one of your Wizard cantrips with a casting time of an action.",
    },
    ("Fighter", "Eldritch Knight", 10): {
        "name": "Eldritch Strike (Eldritch Knight)",
        "description": "When you hit a creature with an attack using a weapon, that creature has Disadvantage on the next saving throw it makes against a spell you cast before the end of your next turn.",
    },
    ("Fighter", "Eldritch Knight", 15): {
        "name": "Arcane Charge (Eldritch Knight)",
        "description": "When you use Action Surge, you can teleport up to 30 feet to an unoccupied space you can see before or after the additional action.",
    },
    ("Fighter", "Eldritch Knight", 18): {
        "name": "Improved War Magic (Eldritch Knight)",
        "description": "When you take the Attack action on your turn, you can replace two of your attacks with a casting of one of your Level 1 or Level 2 Wizard spells that has a casting time of an action.",
    },
    ("Fighter", "Psi Warrior", 3): {
        "name": "Psionic Power (Psi Warrior)",
        "description": "Gain a pool of Psionic Energy Dice (d6) to fuel Protective Field, Psionic Strike, and Telekinetic Movement.",
    },
    ("Fighter", "Psi Warrior", 7): {
        "name": "Telekinetic Adept (Psi Warrior)",
        "description": "Gain Psi-Powered Leap (Fly Speed equal to double Speed until turn end) and Telekinetic Thrust (push or knock target Prone when dealing Psionic Strike damage).",
    },
    ("Fighter", "Psi Warrior", 10): {
        "name": "Guarded Mind (Psi Warrior)",
        "description": "Gain Resistance to Psychic damage, and expend a Psionic Energy Die at the start of your turn to end Charmed and Frightened conditions on yourself.",
    },
    ("Fighter", "Psi Warrior", 15): {
        "name": "Bulwark of Force (Psi Warrior)",
        "description": "As a Bonus Action, grant Half Cover to yourself and allies within 30 feet (up to INT modifier creatures) for 1 minute.",
    },
    ("Fighter", "Psi Warrior", 18): {
        "name": "Telekinetic Master (Psi Warrior)",
        "description": "Always have Telekinesis prepared, cast it once per Long Rest (or by spending a Psionic Energy Die), and make a weapon attack as a Bonus Action while concentrating on it.",
    },
    # ==========================================
    # Barbarian (3, 6, 10, 14)
    # ==========================================
    ("Barbarian", "Path of the Berserker", 3): {
        "name": "Frenzy (Path of the Berserker)",
        "description": "While Raging, hitting with a Strength-based attack while using Reckless Attack deals extra damage on your first hit each turn.",
    },
    ("Barbarian", "Path of the Berserker", 6): {
        "name": "Mindless Rage (Path of the Berserker)",
        "description": "You have Immunity to the Charmed and Frightened conditions while your Rage is active, and entering a Rage ends those conditions on you.",
    },
    ("Barbarian", "Path of the Berserker", 10): {
        "name": "Retaliation (Path of the Berserker)",
        "description": "When you take damage from a creature within 5 feet, use your Reaction to make one melee attack against that creature.",
    },
    ("Barbarian", "Path of the Berserker", 14): {
        "name": "Intimidating Presence (Path of the Berserker)",
        "description": "As a Bonus Action, frighten creatures of your choice within a 30-foot Emanation on a failed WIS save (DC 8 + STR mod + PB) for 1 minute.",
    },
    ("Barbarian", "Path of the Wild Heart", 3): {
        "name": "Animal Speaker & Rage of the Wilds (Path of the Wild Heart)",
        "description": "Learn Beast Sense and Speak with Animals as rituals, and choose Bear, Eagle, or Wolf prowess whenever you enter a Rage.",
    },
    ("Barbarian", "Path of the Wild Heart", 6): {
        "name": "Aspect of the Wilds (Path of the Wild Heart)",
        "description": "Gain Owl Darkvision, Panther Climb Speed, or Salmon Swim Speed (changeable after a Long Rest).",
    },
    ("Barbarian", "Path of the Wild Heart", 10): {
        "name": "Nature Speaker (Path of the Wild Heart)",
        "description": "You always have Commune with Nature prepared and can cast it as a ritual.",
    },
    ("Barbarian", "Path of the Wild Heart", 14): {
        "name": "Power of the Wilds (Path of the Wild Heart)",
        "description": "Whenever you enter Rage, gain Falcon Fly Speed, Lion imposing Disadvantage on adjacent foes' attacks against allies, or Ram knocking Large or smaller targets Prone on melee hits.",
    },
    ("Barbarian", "Path of the World Tree", 3): {
        "name": "Vitality of the Tree (Path of the World Tree)",
        "description": "Gain Temporary Hit Points equal to your Barbarian level upon entering Rage and grant Temporary HP to nearby allies at the start of each turn.",
    },
    ("Barbarian", "Path of the World Tree", 6): {
        "name": "Branches of the Tree (Path of the World Tree)",
        "description": "While Raging, use your Reaction to summon spectral branches that teleport a creature within 30 feet toward you and can reduce its Speed to 0.",
    },
    ("Barbarian", "Path of the World Tree", 10): {
        "name": "Battering Roots (Path of the World Tree)",
        "description": "Your reach increases by 10 feet with Heavy or Versatile melee weapons, and you can apply Push or Topple Weapon Mastery properties on hits.",
    },
    ("Barbarian", "Path of the World Tree", 14): {
        "name": "Travel Along the Tree (Path of the World Tree)",
        "description": "Teleport up to 60 feet as a Bonus Action upon entering Rage or at the start of your turns while Raging, optionally bringing up to six willing allies up to 500 feet once per Rage.",
    },
    ("Barbarian", "Path of the Zealot", 3): {
        "name": "Divine Fury & Warrior of the Gods (Path of the Zealot)",
        "description": "Deal extra Radiant or Necrotic damage on your first hit each turn while Raging, and gain a pool of d12 healing dice usable as a Bonus Action.",
    },
    ("Barbarian", "Path of the Zealot", 6): {
        "name": "Fanatical Focus (Path of the Zealot)",
        "description": "Once per Rage, when you fail a saving throw, you can reroll it with a bonus equal to your Rage Damage bonus.",
    },
    ("Barbarian", "Path of the Zealot", 10): {
        "name": "Zealous Presence (Path of the Zealot)",
        "description": "As a Bonus Action, grant up to 10 allies within 60 feet Advantage on attack rolls and saving throws until the start of your next turn.",
    },
    ("Barbarian", "Path of the Zealot", 14): {
        "name": "Rage of the Gods (Path of the Zealot)",
        "description": "While Raging, assume a divine avatar granting Fly Speed equal to your Speed, Resistance to Necrotic, Psychic, and Radiant damage, and Reaction revivification to 1 HP for nearby allies.",
    },
    # ==========================================
    # Bard (3, 6, 14)
    # ==========================================
    ("Bard", "College of Dance", 3): {
        "name": "Dazzling Footwork (College of Dance)",
        "description": "Calculate unarmored AC as 10 + DEX + CHA modifiers and make an Unarmed Strike using your Bardic Inspiration die when expending Bardic Inspiration.",
    },
    ("Bard", "College of Dance", 6): {
        "name": "Inspiring Movement & Tandem Footwork (College of Dance)",
        "description": "Expend Bardic Inspiration as a Reaction when an enemy moves within 5 feet to move and let an ally move, and add your Bardic Inspiration die to Initiative for yourself and nearby allies.",
    },
    ("Bard", "College of Dance", 14): {
        "name": "Leading Evasion (College of Dance)",
        "description": "Take no damage on a successful DEX save and half damage on a failure, and share that Evasion benefit with allies within 5 feet who aren't Incapacitated.",
    },
    ("Bard", "College of Glamour", 3): {
        "name": "Beguiling Magic & Mantle of Inspiration (College of Glamour)",
        "description": "Always have Charm Person and Mirror Image prepared, and spend Bardic Inspiration as a Bonus Action to grant allies Temporary HP and reaction movement.",
    },
    ("Bard", "College of Glamour", 6): {
        "name": "Mantle of Majesty (College of Glamour)",
        "description": "Always have Command prepared and cast it as a Bonus Action every turn for 1 minute without expending a spell slot (auto-failing Charmed foes).",
    },
    ("Bard", "College of Glamour", 14): {
        "name": "Unbreakable Majesty (College of Glamour)",
        "description": "As a Bonus Action, force creatures attacking you for the next minute to pass a CHA save or miss entirely on the first attack each turn.",
    },
    ("Bard", "College of Lore", 3): {
        "name": "Bonus Proficiencies & Cutting Words (College of Lore)",
        "description": "Gain proficiency in three skills of your choice, and spend Bardic Inspiration as a Reaction to subtract from an enemy's attack roll, ability check, or damage.",
    },
    ("Bard", "College of Lore", 6): {
        "name": "Magical Discoveries (College of Lore)",
        "description": "Learn and always have prepared two spells of your choice from the Cleric, Druid, or Wizard spell lists of a level for which you have spell slots.",
    },
    ("Bard", "College of Lore", 14): {
        "name": "Peerless Skill (College of Lore)",
        "description": "When you make an ability check or attack roll and fail, expend a Bardic Inspiration die and add it to the roll without expending the die if it still fails.",
    },
    ("Bard", "College of Valor", 3): {
        "name": "Combat Inspiration & Martial Training (College of Valor)",
        "description": "Gain proficiency with Medium Armor, Shields, and Martial Weapons, use weapons as Spellcasting Focuses, and empower allies' damage or AC with Bardic Inspiration.",
    },
    ("Bard", "College of Valor", 6): {
        "name": "Extra Attack (College of Valor)",
        "description": "Attack twice when taking the Attack action, and optionally replace one of those attacks with a casting of one of your cantrips.",
    },
    ("Bard", "College of Valor", 14): {
        "name": "Battle Magic (College of Valor)",
        "description": "After casting a spell that has a casting time of an action, make one weapon attack as a Bonus Action.",
    },
    # ==========================================
    # Cleric (3, 6, 17)
    # ==========================================
    ("Cleric", "Life Domain", 3): {
        "name": "Disciple of Life & Preserve Life (Life Domain)",
        "description": "Healing spells you cast with a spell slot restore an additional 2 + spell slot level HP on the turn cast, and you can use Channel Divinity to distribute 5x Cleric level healing.",
    },
    ("Cleric", "Life Domain", 6): {
        "name": "Blessed Healer (Life Domain)",
        "description": "When you cast a healing spell with a spell slot on another creature, you also regain 2 + spell slot level HP.",
    },
    ("Cleric", "Life Domain", 17): {
        "name": "Supreme Healing (Life Domain)",
        "description": "Instead of rolling dice to heal with a spell or Channel Divinity, use the highest number possible for each die.",
    },
    ("Cleric", "Light Domain", 3): {
        "name": "Light Domain Spells, Warding Flare & Radiance of the Dawn (Light Domain)",
        "description": "Always have Light Domain spells prepared, use Warding Flare via Reaction to impose Disadvantage on an attacker within 30 feet, and expend Channel Divinity to dispel magical darkness and deal Radiant damage in a 30-foot Emanation.",
    },
    ("Cleric", "Light Domain", 6): {
        "name": "Improved Warding Flare (Light Domain)",
        "description": "Regain expended uses of Warding Flare on a Short Rest, and grant the target Temporary HP equal to 2d6 + WIS modifier when Warding Flare triggers.",
    },
    ("Cleric", "Light Domain", 17): {
        "name": "Corona of Light (Light Domain)",
        "description": "Emit Sunlight in a 60-foot radius as a Magic action for 1 minute; enemies in the bright light have Disadvantage on saves against your Radiance of the Dawn and Fire/Radiant spells.",
    },
    ("Cleric", "Trickery Domain", 3): {
        "name": "Blessing of the Trickster & Invoke Duplicity (Trickery Domain)",
        "description": "Always have Trickery Domain spells prepared, grant Advantage on Stealth checks, and create an illusory duplicate with Channel Divinity to cast from its space.",
    },
    ("Cleric", "Trickery Domain", 6): {
        "name": "Trickster's Transposition (Trickery Domain)",
        "description": "When creating or moving your Invoke Duplicity illusion as a Bonus Action, you can teleport to swap spaces with it.",
    },
    ("Cleric", "Trickery Domain", 17): {
        "name": "Improved Duplicity (Trickery Domain)",
        "description": "Grant nearby allies Advantage on attack rolls against foes near your illusion, and heal yourself for Cleric level HP when the illusion ends.",
    },
    ("Cleric", "War Domain", 3): {
        "name": "Guided Strike & War Priest (War Domain)",
        "description": "Always have War Domain spells prepared, make Bonus Action weapon attacks WIS mod times per rest, and spend Channel Divinity for +10 to a missed attack roll.",
    },
    ("Cleric", "War Domain", 6): {
        "name": "War God's Blessing (War Domain)",
        "description": "Expend Channel Divinity to cast Shield of Faith or Spiritual Weapon without a spell slot and without requiring Concentration for 1 minute.",
    },
    ("Cleric", "War Domain", 17): {
        "name": "Avatar of Battle (War Domain)",
        "description": "Gain Resistance to Bludgeoning, Piercing, and Slashing damage.",
    },
    # ==========================================
    # Druid (3, 6, 10, 14)
    # ==========================================
    ("Druid", "Circle of the Land", 3): {
        "name": "Circle of the Land Spells & Land's Aid (Circle of the Land)",
        "description": "Attune to an Arid, Polar, Temperate, or Tropical land for prepared spells, and expend Wild Shape to deal Necrotic damage and restore HP in a 10-foot sphere.",
    },
    ("Druid", "Circle of the Land", 6): {
        "name": "Natural Recovery (Circle of the Land)",
        "description": "Cast one of your Circle Spells once per Long Rest without a spell slot, and recover expended spell slots totaling up to half your Druid level on a Short Rest.",
    },
    ("Druid", "Circle of the Land", 10): {
        "name": "Nature's Ward (Circle of the Land)",
        "description": "Gain Immunity to the Poisoned condition and Resistance to the damage type tied to your chosen Land.",
    },
    ("Druid", "Circle of the Land", 14): {
        "name": "Nature's Sanctuary (Circle of the Land)",
        "description": "Expend Wild Shape to create a 15-foot Cube granting allies Half Cover and Resistance matching your chosen Land.",
    },
    ("Druid", "Circle of the Moon", 3): {
        "name": "Circle Forms & Moon Spells (Circle of the Moon)",
        "description": "Assume higher-CR Beast shapes (up to Druid level / 3) with AC equal to 13 + WIS modifier and Temporary HP equal to 3x Druid level.",
    },
    ("Druid", "Circle of the Moon", 6): {
        "name": "Improved Circle Forms (Circle of the Moon)",
        "description": "Your Beast attacks can deal Radiant damage, and you add your WIS modifier to Constitution saving throws while in Wild Shape.",
    },
    ("Druid", "Circle of the Moon", 10): {
        "name": "Moonlight Step (Circle of the Moon)",
        "description": "Teleport up to 30 feet as a Bonus Action WIS modifier times per Long Rest and gain Advantage on your next attack roll.",
    },
    ("Druid", "Circle of the Moon", 14): {
        "name": "Lunar Form (Circle of the Moon)",
        "description": "Add +2d10 Radiant damage once per turn in Wild Shape and bring a willing ally when using Moonlight Step.",
    },
    ("Druid", "Circle of the Sea", 3): {
        "name": "Circle of the Sea Spells & Wrath of the Sea (Circle of the Sea)",
        "description": "Always have Sea spells prepared, and expend Wild Shape as a Bonus Action to create a 5-foot Emanation dealing Cold damage and pushing targets.",
    },
    ("Druid", "Circle of the Sea", 6): {
        "name": "Aquatic Affinity (Circle of the Sea)",
        "description": "Your Wrath of the Sea Emanation grows to 10 feet and grants you a Swim Speed equal to your Speed.",
    },
    ("Druid", "Circle of the Sea", 10): {
        "name": "Stormborn (Circle of the Sea)",
        "description": "While Wrath of the Sea is active, gain a Fly Speed equal to your Speed and Resistance to Cold, Lightning, and Thunder damage.",
    },
    ("Druid", "Circle of the Sea", 14): {
        "name": "Oceanic Gift (Circle of the Sea)",
        "description": "Instead of centering Wrath of the Sea on yourself, surround a willing creature within 60 feet (or split between yourself and an ally with two Wild Shape uses).",
    },
    ("Druid", "Circle of the Stars", 3): {
        "name": "Star Map & Starry Form (Circle of the Stars)",
        "description": "Gain Guidance, Guiding Bolt, and a Star Map focus, and expend Wild Shape as a Bonus Action to assume Archer, Chalice, or Dragon Starry Form.",
    },
    ("Druid", "Circle of the Stars", 6): {
        "name": "Cosmic Omen (Circle of the Stars)",
        "description": "Roll a die after each Long Rest to grant Weal (+1d6) or Woe (-1d6) via Reaction to d20 Tests within 30 feet (PB uses per Long Rest).",
    },
    ("Druid", "Circle of the Stars", 10): {
        "name": "Twinkling Constellations (Circle of the Stars)",
        "description": "Archer and Chalice scale to 2d8, Dragon grants a 20-foot Fly Speed, and you can switch your Starry Form at the start of each turn.",
    },
    ("Druid", "Circle of the Stars", 14): {
        "name": "Full of Stars (Circle of the Stars)",
        "description": "While in Starry Form, you become partially incorporeal and gain Resistance to Bludgeoning, Piercing, and Slashing damage.",
    },
    # ==========================================
    # Monk (3, 6, 11, 17)
    # ==========================================
    ("Monk", "Warrior of Mercy", 3): {
        "name": "Hand of Healing, Hand of Harm & Implements of Mercy (Warrior of Mercy)",
        "description": "Spend Focus Points to heal with Unarmed Strikes or deal extra Necrotic damage, and gain proficiency in Insight, Medicine, and Herbalism Kit.",
    },
    ("Monk", "Warrior of Mercy", 6): {
        "name": "Physician's Touch (Warrior of Mercy)",
        "description": "Hand of Healing also ends Blinded, Deafened, Paralyzed, Poisoned, or Stunned; Hand of Harm inflicts the Poisoned condition without a save.",
    },
    ("Monk", "Warrior of Mercy", 11): {
        "name": "Flurry of Healing and Harm (Warrior of Mercy)",
        "description": "Use Hand of Healing for free during Flurry of Blows and trigger Hand of Harm without spending extra Focus Points while Flurry is active.",
    },
    ("Monk", "Warrior of Mercy", 17): {
        "name": "Hand of Ultimate Mercy (Warrior of Mercy)",
        "description": "Spend 5 Focus Points to restore a creature that died within 24 hours to life with 4d10 + WIS modifier HP.",
    },
    ("Monk", "Warrior of Shadow", 3): {
        "name": "Shadow Arts (Warrior of Shadow)",
        "description": "Gain Darkvision (or extend its range), learn Minor Illusion, and spend 1 Focus Point to cast Darkness that you can see through.",
    },
    ("Monk", "Warrior of Shadow", 6): {
        "name": "Shadow Step (Warrior of Shadow)",
        "description": "As a Bonus Action in Dim Light or Darkness, teleport up to 60 feet to another shadowy space and gain Advantage on your next melee attack.",
    },
    ("Monk", "Warrior of Shadow", 11): {
        "name": "Improved Shadow Step (Warrior of Shadow)",
        "description": "Spend 1 Focus Point when using Shadow Step to ignore the Dim Light or Darkness origin/destination requirement and follow immediately with an Unarmed Strike.",
    },
    ("Monk", "Warrior of Shadow", 17): {
        "name": "Cloak of Shadows (Warrior of Shadow)",
        "description": "Spend 3 Focus Points in Dim Light or Darkness to become Invisible and move through solid objects and creatures for 1 minute.",
    },
    ("Monk", "Warrior of the Elements", 3): {
        "name": "Elemental Attunement & Manipulate Elements (Warrior of the Elements)",
        "description": "Learn Elementalism and spend 1 Focus Point for 15-foot reach Unarmed Strikes dealing Acid, Cold, Fire, Lightning, or Thunder damage with forced movement.",
    },
    ("Monk", "Warrior of the Elements", 6): {
        "name": "Elemental Burst (Warrior of the Elements)",
        "description": "Spend 2 Focus Points to unleash a 20-foot-radius Elemental burst dealing 3 Martial Arts dice of Acid, Cold, Fire, Lightning, or Thunder damage.",
    },
    ("Monk", "Warrior of the Elements", 11): {
        "name": "Stride of the Elements (Warrior of the Elements)",
        "description": "While Elemental Attunement is active, gain a Fly Speed and Swim Speed equal to your Speed.",
    },
    ("Monk", "Warrior of the Elements", 17): {
        "name": "Elemental Epitome (Warrior of the Elements)",
        "description": "Gain Resistance to a chosen elemental type, +20 Speed during Step of the Wind leaving elemental bursts, and +1 Martial Arts die elemental damage once per turn.",
    },
    ("Monk", "Warrior of the Open Hand", 3): {
        "name": "Open Hand Technique (Warrior of the Open Hand)",
        "description": "Whenever you hit with Flurry of Blows, impose Addle (preventing Opportunity Attacks), Push (15 ft on failed STR save), or Topple (Prone on failed DEX save).",
    },
    ("Monk", "Warrior of the Open Hand", 6): {
        "name": "Wholeness of Body (Warrior of the Open Hand)",
        "description": "As a Bonus Action, regain HP equal to your Martial Arts die + WIS modifier (WIS modifier uses per Long Rest).",
    },
    ("Monk", "Warrior of the Open Hand", 11): {
        "name": "Fleet Step (Warrior of the Open Hand)",
        "description": "Whenever you take a Bonus Action other than Step of the Wind, you can immediately take Step of the Wind as well.",
    },
    ("Monk", "Warrior of the Open Hand", 17): {
        "name": "Quivering Palm (Warrior of the Open Hand)",
        "description": "Spend 4 Focus Points on an Unarmed Strike to set lethal vibrations that deal 10d12 Force damage (half on CON save) when ended.",
    },
    # ==========================================
    # Paladin (3, 7, 15, 20)
    # ==========================================
    ("Paladin", "Oath of Devotion", 3): {
        "name": "Sacred Weapon & Devotion Spells (Oath of Devotion)",
        "description": "Keep Devotion spells prepared and expend Channel Divinity as part of an attack to add your CHA modifier to weapon attack rolls and emit bright light.",
    },
    ("Paladin", "Oath of Devotion", 7): {
        "name": "Aura of Devotion (Oath of Devotion)",
        "description": "You and allies inside your Aura of Protection have Immunity to the Charmed condition.",
    },
    ("Paladin", "Oath of Devotion", 15): {
        "name": "Smite of Protection (Oath of Devotion)",
        "description": "Whenever you cast Divine Smite, you and allies in your Aura of Protection gain Half Cover until the start of your next turn.",
    },
    ("Paladin", "Oath of Devotion", 20): {
        "name": "Holy Nimbus (Oath of Devotion)",
        "description": "Emit Sunlight for 10 minutes as a Bonus Action, granting Advantage on saves against Fiend/Undead spells and dealing CHA mod + PB Radiant damage in your aura.",
    },
    ("Paladin", "Oath of Glory", 3): {
        "name": "Inspiring Smite & Peerless Athlete (Oath of Glory)",
        "description": "Keep Glory spells prepared and spend Channel Divinity for athletic prowess or to grant Temporary HP after casting Divine Smite.",
    },
    ("Paladin", "Oath of Glory", 7): {
        "name": "Aura of Alacrity (Oath of Glory)",
        "description": "Your Speed increases by 10 feet, and any ally who enters your Aura of Protection gains +10 feet Speed until the end of their next turn.",
    },
    ("Paladin", "Oath of Glory", 15): {
        "name": "Glorious Defense (Oath of Glory)",
        "description": "Use your Reaction to add CHA modifier to a nearby ally's AC against an attack and counterattack the attacker if it misses (CHA mod uses per Long Rest).",
    },
    ("Paladin", "Oath of Glory", 20): {
        "name": "Living Legend (Oath of Glory)",
        "description": "For 10 minutes as a Bonus Action, gain Advantage on CHA checks, turn missed weapon attacks into hits, and reroll failed saving throws via Reaction.",
    },
    ("Paladin", "Oath of the Ancients", 3): {
        "name": "Nature's Wrath & Ancients Spells (Oath of the Ancients)",
        "description": "Keep Ancients spells prepared and expend Channel Divinity as a Magic action to conjure spectral vines that restrain nearby creatures.",
    },
    ("Paladin", "Oath of the Ancients", 7): {
        "name": "Aura of Warding (Oath of the Ancients)",
        "description": "You and allies inside your Aura of Protection gain Resistance to Necrotic, Psychic, and Radiant damage.",
    },
    ("Paladin", "Oath of the Ancients", 15): {
        "name": "Undying Sentinel (Oath of the Ancients)",
        "description": "When dropped to 0 HP (not killed outright), drop to 1 HP instead and regain HP equal to 3x Paladin level once per Long Rest, and stop aging magically.",
    },
    ("Paladin", "Oath of the Ancients", 20): {
        "name": "Elder Champion (Oath of the Ancients)",
        "description": "For 1 minute as a Bonus Action, regain 10 HP per turn, cast action spells as Bonus Actions, and impose Disadvantage on saves vs Paladin spells in your aura.",
    },
    ("Paladin", "Oath of Vengeance", 3): {
        "name": "Vow of Enmity & Vengeance Spells (Oath of Vengeance)",
        "description": "Keep Vengeance spells prepared and expend Channel Divinity when hitting an enemy to gain Advantage on attacks against it for 1 minute.",
    },
    ("Paladin", "Oath of Vengeance", 7): {
        "name": "Relentless Avenger (Oath of Vengeance)",
        "description": "When you hit with an Opportunity Attack, reduce the target's Speed to 0 and move up to half your Speed without provoking Opportunity Attacks.",
    },
    ("Paladin", "Oath of Vengeance", 15): {
        "name": "Soul of Vengeance (Oath of Vengeance)",
        "description": "Use your Reaction to make an attack when the creature targeted by your Vow of Enmity makes an attack roll.",
    },
    ("Paladin", "Oath of Vengeance", 20): {
        "name": "Avenging Angel (Oath of Vengeance)",
        "description": "For 10 minutes as a Bonus Action, gain a 60-foot Fly Speed and a 30-foot Frightening aura granting Advantage on attacks against frightened foes.",
    },
    # ==========================================
    # Ranger (3, 7, 11, 15)
    # ==========================================
    ("Ranger", "Beast Master", 3): {
        "name": "Primal Companion (Beast Master)",
        "description": "Bond with a Beast of the Land, Sea, or Sky that acts on your turn and strikes when you command it with a Bonus Action or Attack sacrifice.",
    },
    ("Ranger", "Beast Master", 7): {
        "name": "Exceptional Training (Beast Master)",
        "description": "Your Primal Companion can Dash, Disengage, Dodge, or Help as a Bonus Action, and its strikes deal Force or normal damage.",
    },
    ("Ranger", "Beast Master", 11): {
        "name": "Bestial Fury (Beast Master)",
        "description": "Your Primal Companion makes two Beast's Strike attacks when commanded and deals bonus Hunter's Mark force damage once per turn.",
    },
    ("Ranger", "Beast Master", 15): {
        "name": "Share Spells (Beast Master)",
        "description": "Spells you cast targeting yourself also affect your Primal Companion if within 30 feet.",
    },
    ("Ranger", "Fey Wanderer", 3): {
        "name": "Dreadful Strikes & Otherworldly Glamour (Fey Wanderer)",
        "description": "Deal an extra 1d4 Psychic damage once per turn per target on weapon hits, add your WIS modifier to Charisma checks, and prepare Fey Wanderer spells.",
    },
    ("Ranger", "Fey Wanderer", 7): {
        "name": "Beguiling Twist (Fey Wanderer)",
        "description": "Gain Advantage on saves vs Charmed/Frightened, and use your Reaction when a nearby creature saves against those conditions to bounce it to another creature.",
    },
    ("Ranger", "Fey Wanderer", 11): {
        "name": "Fey Reinforcements (Fey Wanderer)",
        "description": "Always have Summon Fey prepared, cast it once per Long Rest without a slot, and optionally cast it without Concentration lasting 1 minute.",
    },
    ("Ranger", "Fey Wanderer", 15): {
        "name": "Misty Wanderer (Fey Wanderer)",
        "description": "Always have Misty Step prepared, cast it WIS modifier times per Long Rest, and bring one willing ally within 5 feet with you.",
    },
    ("Ranger", "Gloom Stalker", 3): {
        "name": "Dread Ambusher & Umbral Sight (Gloom Stalker)",
        "description": "Add your WIS modifier to Initiative, gain Darkvision (and invisibility to Darkvision in darkness), keep Gloom Stalker spells prepared, and empower Dread Ambusher strikes.",
    },
    ("Ranger", "Gloom Stalker", 7): {
        "name": "Iron Mind (Gloom Stalker)",
        "description": "Gain proficiency in Wisdom saving throws (or INT/CHA if already proficient).",
    },
    ("Ranger", "Gloom Stalker", 11): {
        "name": "Stalker's Flurry (Gloom Stalker)",
        "description": "Dreadful Strike scales to 2d8 Psychic damage and triggers Sudden Strike (additional attack) or Mass Fear around the target.",
    },
    ("Ranger", "Gloom Stalker", 15): {
        "name": "Shadowy Dodge (Gloom Stalker)",
        "description": "Use your Reaction to impose Disadvantage on an incoming attack roll against you and teleport 30 feet if the attack misses.",
    },
    ("Ranger", "Hunter", 3): {
        "name": "Hunter's Lore & Hunter's Prey (Hunter)",
        "description": "Learn a Hunter's Mark target's immunities, resistances, and vulnerabilities, and choose Colossus Slayer or Horde Breaker.",
    },
    ("Ranger", "Hunter", 7): {
        "name": "Defensive Tactics (Hunter)",
        "description": "Choose Escape the Horde (Opportunity Attacks have Disadvantage against you) or Multiattack Defense (when a creature hits you, it has Disadvantage on all other attack rolls against you this turn); you can change your choice after a Short or Long Rest.",
    },
    ("Ranger", "Hunter", 11): {
        "name": "Superior Hunter's Prey (Hunter)",
        "description": "Once per turn when dealing Hunter's Prey damage to a marked target, deal equal damage to another creature within 30 feet of it.",
    },
    ("Ranger", "Hunter", 15): {
        "name": "Superior Hunter's Defense (Hunter)",
        "description": "When you take damage, use your Reaction to give yourself Resistance to that damage and to any other damage of the same type until the end of the current turn.",
    },
    # ==========================================
    # Rogue (3, 9, 13, 17)
    # ==========================================
    ("Rogue", "Thief", 3): {
        "name": "Fast Hands & Second-Story Work (Thief)",
        "description": "Use your Cunning Action Bonus Action to make Sleight of Hand checks, use Thieves' Tools, or take the Utilize/Magic action with an item, and gain a Climb Speed equal to your Speed.",
    },
    ("Rogue", "Thief", 9): {
        "name": "Supreme Sneak (Thief)",
        "description": "Use the Stealth Attack Cunning Strike option (1d6) to remain Hidden after attacking if you end your turn behind Three-Quarters or Total Cover.",
    },
    ("Rogue", "Thief", 13): {
        "name": "Use Magic Device (Thief)",
        "description": "Attune to up to four magic items, occasionally expend charges without draining them (on a 6 on 1d6), and use any Spell Scroll.",
    },
    ("Rogue", "Thief", 17): {
        "name": "Thief's Reflexes (Thief)",
        "description": "Take two turns during the first round of any combat (the second at your Initiative minus 10).",
    },
    ("Rogue", "Arcane Trickster", 3): {
        "name": "Spellcasting & Mage Hand Legerdemain (Arcane Trickster)",
        "description": "Cast Wizard spells (INT) and summon an invisible Mage Hand capable of stowing, retrieving, picking locks, and disarming traps remotely.",
    },
    ("Rogue", "Arcane Trickster", 9): {
        "name": "Magical Ambush (Arcane Trickster)",
        "description": "If you have the Invisible condition when casting a spell on your turn, targets have Disadvantage on their first saving throw against it.",
    },
    ("Rogue", "Arcane Trickster", 13): {
        "name": "Versatile Trickster (Arcane Trickster)",
        "description": "When you use the Trip Cunning Strike option, your Mage Hand can distract another nearby target to trigger Sneak Attack.",
    },
    ("Rogue", "Arcane Trickster", 17): {
        "name": "Spell Thief (Arcane Trickster)",
        "description": "When targeted by a spell, use your Reaction to negate its effect on you and steal the knowledge to cast it for 8 hours (once per Long Rest).",
    },
    ("Rogue", "Assassin", 3): {
        "name": "Assassinate & Assassin's Tools (Assassin)",
        "description": "Gain Advantage on Initiative and first-round attacks against creatures that haven't acted (with extra Rogue-level damage on Sneak Attack), plus Disguise and Poisoner's Kit proficiency.",
    },
    ("Rogue", "Assassin", 9): {
        "name": "Infiltration Expertise (Assassin)",
        "description": "Adopt convincing false identities via Masterful Mimicry and move at normal speed while maintaining Advantage on attack rolls with Steady Aim.",
    },
    ("Rogue", "Assassin", 13): {
        "name": "Envenom Weapons (Assassin)",
        "description": "When using the Poison Cunning Strike option, the target takes an extra 2d6 Poison damage ignoring Poison Resistance.",
    },
    ("Rogue", "Assassin", 17): {
        "name": "Death Strike (Assassin)",
        "description": "Targets hit on the first round of combat must make a CON save or suffer doubled damage from that attack.",
    },
    ("Rogue", "Soulknife", 3): {
        "name": "Psionic Power & Psychic Blades (Soulknife)",
        "description": "Gain Psionic Energy Dice (d6) for Psi-Bolstered Knack and Psychic Whispers, and manifest melee or thrown Psychic Blades dealing Psychic damage.",
    },
    ("Rogue", "Soulknife", 9): {
        "name": "Soul Blades (Soulknife)",
        "description": "Spend a Psionic Energy Die for Homing Strikes (+die to missed Psychic Blade attack) or Psychic Teleportation (teleport 10x die feet as a Bonus Action).",
    },
    ("Rogue", "Soulknife", 13): {
        "name": "Psychic Veil (Soulknife)",
        "description": "Become Invisible for 1 hour as a Magic action (once per Long Rest or by expending a Psionic Energy Die).",
    },
    ("Rogue", "Soulknife", 17): {
        "name": "Rend Mind (Soulknife)",
        "description": "Force a target damaged by Psychic Blades Sneak Attack to succeed on a WIS save or be Stunned for 1 minute (once per Long Rest or 3 Psionic Dice).",
    },
    # ==========================================
    # Sorcerer (3, 6, 14, 18)
    # ==========================================
    ("Sorcerer", "Draconic Sorcery", 3): {
        "name": "Draconic Resilience & Draconic Spells (Draconic Sorcery)",
        "description": "Your HP maximum increases by 3 (and by 1 whenever you gain another Sorcerer level), your unarmored AC equals 10 + DEX + CHA modifiers, and you always have your Draconic Spells prepared.",
    },
    ("Sorcerer", "Draconic Sorcery", 6): {
        "name": "Elemental Affinity (Draconic Sorcery)",
        "description": "Gain Resistance to the damage type of your Draconic Ancestry, and add your CHA modifier to one damage roll of any spell you cast that deals that damage type.",
    },
    ("Sorcerer", "Draconic Sorcery", 14): {
        "name": "Dragon Wings (Draconic Sorcery)",
        "description": "As a Bonus Action, manifest spectral dragon wings granting a Fly Speed of 60 feet for 1 hour (once per Long Rest or by spending 3 Sorcery Points).",
    },
    ("Sorcerer", "Draconic Sorcery", 18): {
        "name": "Dragon Companion (Draconic Sorcery)",
        "description": "Cast Summon Dragon once per Long Rest without material components, optionally removing Concentration for a 1-minute duration.",
    },
    ("Sorcerer", "Aberrant Sorcery", 3): {
        "name": "Psionic Spells & Telepathic Speech (Aberrant Sorcery)",
        "description": "Always have Aberrant psionic spells prepared, and link minds as a Bonus Action to communicate telepathically within 30 feet.",
    },
    ("Sorcerer", "Aberrant Sorcery", 6): {
        "name": "Psionic Sorcery (Aberrant Sorcery)",
        "description": "Cast Psionic Spells by spending Sorcery Points equal to the spell's level, ignoring Verbal/Somatic and non-consumed Material components.",
    },
    ("Sorcerer", "Aberrant Sorcery", 14): {
        "name": "Revelation in Flesh (Aberrant Sorcery)",
        "description": "Spend Sorcery Points as a Bonus Action for 10 minutes to gain See Invisibility, Fly Speed with hover, Swim Speed/water breathing, or squeeze through 1-inch spaces.",
    },
    ("Sorcerer", "Aberrant Sorcery", 18): {
        "name": "Warping Implosion (Aberrant Sorcery)",
        "description": "Teleport up to 120 feet as a Magic action, creating a gravity anomaly that pulls nearby creatures in for 3d10 Force damage (once per Long Rest or 5 Sorcery Points).",
    },
    ("Sorcerer", "Clockwork Sorcery", 3): {
        "name": "Clockwork Spells & Restore Balance (Clockwork Sorcery)",
        "description": "Always have Clockwork spells prepared, and use your Reaction to cancel Advantage or Disadvantage on a d20 Test within 60 feet.",
    },
    ("Sorcerer", "Clockwork Sorcery", 6): {
        "name": "Bastion of Law (Clockwork Sorcery)",
        "description": "Spend 1 to 5 Sorcery Points as a Magic action to create a ward of d8s that a creature can spend as a Reaction to reduce incoming damage.",
    },
    ("Sorcerer", "Clockwork Sorcery", 14): {
        "name": "Trance of Order (Clockwork Sorcery)",
        "description": "For 1 minute as a Bonus Action, attacks against you cannot benefit from Advantage and your d20 Tests treat any roll of 9 or lower as a 10.",
    },
    ("Sorcerer", "Clockwork Sorcery", 18): {
        "name": "Clockwork Cavalcade (Clockwork Sorcery)",
        "description": "Restore up to 100 total HP, repair objects, and end Level 6 or lower spells in a 30-foot Cube as a Magic action (once per Long Rest or 7 Sorcery Points).",
    },
    ("Sorcerer", "Wild Magic Sorcery", 3): {
        "name": "Wild Magic Surge & Tides of Chaos (Wild Magic Sorcery)",
        "description": "Trigger Wild Magic Surge effects after leveled Sorcerer spells and claim Advantage on one d20 Test via Tides of Chaos.",
    },
    ("Sorcerer", "Wild Magic Sorcery", 6): {
        "name": "Bend Luck (Wild Magic Sorcery)",
        "description": "Use your Reaction and spend 1 Sorcery Point to roll 1d4 and add or subtract it from another creature's d20 Test within 30 feet.",
    },
    ("Sorcerer", "Wild Magic Sorcery", 14): {
        "name": "Controlled Chaos (Wild Magic Sorcery)",
        "description": "Roll twice on the Wild Magic Surge table whenever you trigger a surge and choose either outcome.",
    },
    ("Sorcerer", "Wild Magic Sorcery", 18): {
        "name": "Tamed Surge (Wild Magic Sorcery)",
        "description": "Once per Long Rest, pick any non-self-buff effect from the Wild Magic Surge table immediately after casting a Sorcerer spell with a spell slot.",
    },
    ("Sorcerer", "Wild Magic", 3): {
        "name": "Wild Magic Surge & Tides of Chaos (Wild Magic)",
        "description": "Trigger Wild Magic Surge effects after leveled Sorcerer spells and claim Advantage on one d20 Test via Tides of Chaos.",
    },
    ("Sorcerer", "Wild Magic", 6): {
        "name": "Bend Luck (Wild Magic)",
        "description": "Use your Reaction and spend 1 Sorcery Point to roll 1d4 and add or subtract it from another creature's d20 Test within 30 feet.",
    },
    ("Sorcerer", "Wild Magic", 14): {
        "name": "Controlled Chaos (Wild Magic)",
        "description": "Roll twice on the Wild Magic Surge table whenever you trigger a surge and choose either outcome.",
    },
    ("Sorcerer", "Wild Magic", 18): {
        "name": "Tamed Surge (Wild Magic)",
        "description": "Once per Long Rest, pick any non-self-buff effect from the Wild Magic Surge table immediately after casting a Sorcerer spell with a spell slot.",
    },
    # ==========================================
    # Warlock (3, 6, 10, 14)
    # ==========================================
    ("Warlock", "Archfey Patron", 3): {
        "name": "Archfey Spells & Steps of the Fey (Archfey Patron)",
        "description": "Always have Archfey spells prepared and cast Misty Step CHA modifier times per Long Rest with fey teleportation effects.",
    },
    ("Warlock", "Archfey Patron", 6): {
        "name": "Misty Escape (Archfey Patron)",
        "description": "Cast Misty Step as a Reaction when taking damage, adding Disappearing Step (invisible) or Dreadful Step (2d10 Psychic damage).",
    },
    ("Warlock", "Archfey Patron", 10): {
        "name": "Beguiling Defenses (Archfey Patron)",
        "description": "Gain Immunity to Charmed, and use your Reaction to grant Resistance to incoming damage while bouncing 2d10 Psychic damage back at the attacker.",
    },
    ("Warlock", "Archfey Patron", 14): {
        "name": "Bewitching Magic (Archfey Patron)",
        "description": "Immediately cast Misty Step without a slot after casting an Enchantment or Illusion spell with a spell slot.",
    },
    ("Warlock", "Celestial Patron", 3): {
        "name": "Celestial Spells & Healing Light (Celestial Patron)",
        "description": "Gain Sacred Flame and Light, keep Celestial spells prepared, and spend d6s from a Healing Light pool as a Bonus Action.",
    },
    ("Warlock", "Celestial Patron", 6): {
        "name": "Radiant Soul (Celestial Patron)",
        "description": "Gain Resistance to Radiant damage, and once per turn add your CHA modifier to Fire or Radiant spell damage.",
    },
    ("Warlock", "Celestial Patron", 10): {
        "name": "Celestial Resilience (Celestial Patron)",
        "description": "After a Short or Long Rest (or Magical Cunning), grant yourself Temporary HP equal to Warlock level + CHA mod and up to 5 allies half Warlock level + CHA mod.",
    },
    ("Warlock", "Celestial Patron", 14): {
        "name": "Searing Vengeance (Celestial Patron)",
        "description": "When making a Death Save, regain half your HP max, stand up, and deal 2d8 + CHA mod Radiant damage plus Blindness to nearby foes (once per Long Rest).",
    },
    ("Warlock", "Fiend Patron", 3): {
        "name": "Dark One's Blessing & Fiend Spells (Fiend Patron)",
        "description": "Always have Fiend spells prepared and gain Temporary HP equal to CHA modifier + Warlock level when a nearby enemy falls to 0 HP.",
    },
    ("Warlock", "Fiend Patron", 6): {
        "name": "Dark One's Own Luck (Fiend Patron)",
        "description": "Add 1d10 to an ability check or saving throw after seeing the roll (CHA modifier uses per Long Rest).",
    },
    ("Warlock", "Fiend Patron", 10): {
        "name": "Fiendish Resilience (Fiend Patron)",
        "description": "Choose one damage type other than Force after each Short or Long Rest and gain Resistance to it.",
    },
    ("Warlock", "Fiend Patron", 14): {
        "name": "Hurl Through Hell (Fiend Patron)",
        "description": "Once per Long Rest (or by expending a Pact slot), banish a hit target through the lower planes for 8d10 Psychic damage and Incapacitation.",
    },
    ("Warlock", "Great Old One Patron", 3): {
        "name": "Awakened Mind & Psychic Spells (Great Old One Patron)",
        "description": "Always have Great Old One spells prepared, communicate telepathically, omit Verbal/Somatic components on Illusion/Enchantment spells, and swap spell damage to Psychic.",
    },
    ("Warlock", "Great Old One Patron", 6): {
        "name": "Clairvoyant Combatant (Great Old One Patron)",
        "description": "A creature linked via Awakened Mind suffers Disadvantage on attacks against you while you gain Advantage on attacks against it (once per Short/Long Rest).",
    },
    ("Warlock", "Great Old One Patron", 10): {
        "name": "Eldritch Hex & Thought Shield (Great Old One Patron)",
        "description": "Gain Resistance to Psychic damage, prevent mind-reading, and impose Disadvantage on one ability's saving throws via Hex.",
    },
    ("Warlock", "Great Old One Patron", 14): {
        "name": "Create Thrall (Great Old One Patron)",
        "description": "Always have Summon Aberration prepared and summon an Aberration without Concentration (with bonus Temporary HP) for 1 minute.",
    },
    # ==========================================
    # Wizard (3, 6, 10, 14)
    # ==========================================
    ("Wizard", "School of Evocation", 3): {
        "name": "Evocation Savant & Potent Cantrip (School of Evocation)",
        "description": "Gain two Evocation spells in your spellbook, and when you miss with your cantrip attack roll or a target succeeds on its saving throw against your damaging cantrip, it still takes half damage.",
    },
    ("Wizard", "Evoker", 3): {
        "name": "Evocation Savant & Potent Cantrip (Evoker)",
        "description": "Gain two Evocation spells in your spellbook, and when you miss with your cantrip attack roll or a target succeeds on its saving throw against your damaging cantrip, it still takes half damage.",
    },
    ("Wizard", "Evoker", 6): {
        "name": "Sculpt Spells (Evoker)",
        "description": "Create pockets of safety in your Evocation spells so chosen creatures automatically succeed on their saving throws and take no damage.",
    },
    ("Wizard", "Evoker", 10): {
        "name": "Empowered Evocation (Evoker)",
        "description": "Add your Intelligence modifier to one damage roll of any Wizard Evocation spell you cast.",
    },
    ("Wizard", "Evoker", 14): {
        "name": "Overchannel (Evoker)",
        "description": "Deal maximum damage with a Level 1–5 Wizard spell once per Long Rest (subsequent uses deal self-damage unless rested).",
    },
    ("Wizard", "School of Evocation", 6): {
        "name": "Sculpt Spells (School of Evocation)",
        "description": "Create pockets of safety in your Evocation spells so chosen creatures automatically succeed on their saving throws and take no damage.",
    },
    ("Wizard", "School of Evocation", 10): {
        "name": "Empowered Evocation (School of Evocation)",
        "description": "Add your Intelligence modifier to one damage roll of any Wizard Evocation spell you cast.",
    },
    ("Wizard", "School of Evocation", 14): {
        "name": "Overchannel (School of Evocation)",
        "description": "Deal maximum damage with a Level 1–5 Wizard spell once per Long Rest (subsequent uses deal self-damage unless rested).",
    },
    ("Wizard", "Abjurer", 3): {
        "name": "Abjuration Savant & Arcane Ward (Abjurer)",
        "description": "Gain two Abjuration spells in your spellbook and weave a magical Arcane Ward that absorbs damage whenever you cast Abjuration spells.",
    },
    ("Wizard", "Abjurer", 6): {
        "name": "Projected Ward (Abjurer)",
        "description": "Use your Reaction when a creature within 30 feet takes damage to have your Arcane Ward absorb that damage instead.",
    },
    ("Wizard", "Abjurer", 10): {
        "name": "Spell Breaker (Abjurer)",
        "description": "Always have Counterspell and Dispel Magic prepared, cast Dispel Magic as a Bonus Action adding PB to the check, and retain spell slots when a dispel/counter fails.",
    },
    ("Wizard", "Abjurer", 14): {
        "name": "Spell Resistance (Abjurer)",
        "description": "You have Advantage on saving throws against spells and Resistance to the damage of spells.",
    },
    ("Wizard", "Diviner", 3): {
        "name": "Divination Savant & Portent (Diviner)",
        "description": "Gain two Divination spells in your spellbook and roll two d20 Portent dice after a Long Rest to replace d20 Tests made by you or visible creatures.",
    },
    ("Wizard", "Diviner", 6): {
        "name": "Expert Divination (Diviner)",
        "description": "Casting a Divination spell of Level 2 or higher with a spell slot regains an expended spell slot of lower level (up to Level 5).",
    },
    ("Wizard", "Diviner", 10): {
        "name": "The Third Eye (Diviner)",
        "description": "As a Bonus Action, gain Darkvision (120 ft), Ethereal Sight, Greater Comprehension, or See Invisibility until your next rest.",
    },
    ("Wizard", "Diviner", 14): {
        "name": "Greater Portent (Diviner)",
        "description": "Roll three d20s for your Portent feature instead of two.",
    },
    ("Wizard", "Illusionist", 3): {
        "name": "Illusion Savant & Improved Illusions (Illusionist)",
        "description": "Gain two Illusion spells in your spellbook, cast Illusion spells without Verbal components, enhance Minor Illusion, and cast Summon Beast/Fey as illusions.",
    },
    ("Wizard", "Illusionist", 6): {
        "name": "Phantasmal Creatures (Illusionist)",
        "description": "Always have Summon Beast and Summon Fey prepared, and cast either once per Long Rest without a spell slot (half HP, Illusion school).",
    },
    ("Wizard", "Illusionist", 10): {
        "name": "Illusory Self (Illusionist)",
        "description": "Use your Reaction when hit by an attack roll to force the attack to miss via an illusory double (recharges on Short/Long Rest or Level 2+ spell slot).",
    },
    ("Wizard", "Illusionist", 14): {
        "name": "Illusory Reality (Illusionist)",
        "description": "As a Bonus Action, make one inanimate, nonmagical object inside a Level 1+ Illusion spell you cast temporarily real for 1 minute.",
    },
    # ==========================================
    # Artificer (3, 6, 10, 14)
    # ==========================================
    ("Artificer", "Alchemist", 3): {
        "name": "Experimental Elixir & Tool Proficiency (Alchemist)",
        "description": "Gain Alchemist's Supplies proficiency and brew Experimental Elixirs after a Long Rest or by expending spell slots.",
    },
    ("Artificer", "Alchemist", 6): {
        "name": "Alchemical Savant (Alchemist)",
        "description": "When casting an Artificer spell through Alchemist's Supplies, add your INT modifier to one healing roll or Acid, Fire, Necrotic, or Poison damage roll.",
    },
    ("Artificer", "Alchemist", 10): {
        "name": "Restorative Reagents (Alchemist)",
        "description": "Experimental Elixirs grant bonus Temporary HP, and you can cast Lesser Restoration INT modifier times per Long Rest without a slot.",
    },
    ("Artificer", "Alchemist", 14): {
        "name": "Chemical Mastery (Alchemist)",
        "description": "Gain Resistance to Acid and Poison damage and Immunity to the Poisoned condition, and cast Greater Restoration and Heal once per Long Rest without slots.",
    },
    ("Artificer", "Armorer", 3): {
        "name": "Arcane Armor & Tools of the Trade (Armorer)",
        "description": "Gain Heavy Armor and Smith's Tools proficiency and transform armor into Guardian or Infiltrator Arcane Armor.",
    },
    ("Artificer", "Armorer", 6): {
        "name": "Armor Modifications (Armorer)",
        "description": "Your Arcane Armor separates into distinct boots, bracers, chestpiece, and weapon slots for Plans/Replicate Magic Item and increases your known magic item plans.",
    },
    ("Artificer", "Armorer", 10): {
        "name": "Improved Arcane Armor (Armorer)",
        "description": "Enhance your Arcane Armor's model weapon strikes and defensive capabilities across Guardian and Infiltrator modes.",
    },
    ("Artificer", "Armorer", 14): {
        "name": "Perfected Armor (Armorer)",
        "description": "Maximize your Guardian/Infiltrator Arcane Armor effects, pulling foes into melee or unleashing intensified lightning strikes.",
    },
    ("Artificer", "Artillerist", 3): {
        "name": "Eldritch Cannon & Artillerist Spells (Artillerist)",
        "description": "Gain Woodcarver's Tools proficiency, prepare Artillerist spells, and summon a Magical Eldritch Cannon (Flamethrower, Force Ballista, or Protector).",
    },
    ("Artificer", "Artillerist", 6): {
        "name": "Arcane Firearm (Artillerist)",
        "description": "Inscribe a wand, staff, or rod as an Arcane Firearm to add 1d8 extra damage to one damage roll of your Artificer spells.",
    },
    ("Artificer", "Artillerist", 10): {
        "name": "Explosive Cannon (Artillerist)",
        "description": "Your Eldritch Cannon damage/healing rolls scale by +1d8, and you can command it to detonate in a 20-foot-radius Force blast.",
    },
    ("Artificer", "Artillerist", 14): {
        "name": "Fortified Position (Artillerist)",
        "description": "Maintain two Eldritch Cannons at once and grant Half Cover to yourself and allies within 10 feet of them.",
    },
    ("Artificer", "Battle Smith", 3): {
        "name": "Battle Ready & Steel Defender (Battle Smith)",
        "description": "Use INT for magic weapon attacks, gain Smith's Tools proficiency, keep Battle Smith spells prepared, and command a Steel Defender companion.",
    },
    ("Artificer", "Battle Smith", 6): {
        "name": "Arcane Jolt (Battle Smith)",
        "description": "Channel stored magic on weapon or Steel Defender hits to deal extra Force damage or heal an ally within 30 feet (INT mod uses per Long Rest).",
    },
    ("Artificer", "Battle Smith", 10): {
        "name": "Steel Defender Resilience (Battle Smith)",
        "description": "Further empower your Steel Defender and Arcane Jolt support for frontline protection.",
    },
    ("Artificer", "Battle Smith", 14): {
        "name": "Improved Defender (Battle Smith)",
        "description": "Arcane Jolt scales to 4d6, your Steel Defender gains +2 AC, and Deflect Attack deals 1d4 + INT modifier Force damage.",
    },
    ("Artificer", "Cartographer", 3): {
        "name": "Tools of the Trade & Adventurer's Atlas (Cartographer)",
        "description": "Gain Calligrapher's Supplies and Cartographer's Tools proficiency (halving Spell Scroll scribing time and cost), keep Cartographer spells prepared, and link allies with Adventurer's Atlas maps.",
    },
    ("Artificer", "Cartographer", 6): {
        "name": "Guided Precision & Portal Jump (Cartographer)",
        "description": "Enhance Adventurer's Atlas allies with extra precision and short-range spatial repositioning between mapped coordinates.",
    },
    ("Artificer", "Cartographer", 10): {
        "name": "Ingenious Movement (Cartographer)",
        "description": "Use your Flash of Genius or Atlas links to help allies escape danger and traverse battlefield hazards effortlessly.",
    },
    ("Artificer", "Cartographer", 14): {
        "name": "Superior Atlas (Cartographer)",
        "description": "Protect your Adventurer's Atlas holders from lethal hits with emergency rescue teleports and expand your magical cartography network.",
    },
}

KNOWN_SUBCLASS_FEATURES_2024: dict[tuple[str, str, int], str] = {
    k: v["name"] for k, v in SUBCLASS_FEATURES_DETAILS_2024.items()
}
