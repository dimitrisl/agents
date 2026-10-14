export interface ClassSkillRules {
  allowed: string[];
  recommended: string[];
  count: number;
}

export const ALL_DND_SKILLS = [
  { name: 'Acrobatics', ability: 'DEX', description: 'Agility, balance, and tumbling.' },
  { name: 'Animal Handling', ability: 'WIS', description: 'Calming or controlling animals.' },
  { name: 'Arcana', ability: 'INT', description: 'Lore on spells, magic items, and planes.' },
  { name: 'Athletics', ability: 'STR', description: 'Climbing, jumping, swimming, and grappling.' },
  { name: 'Deception', ability: 'CHA', description: 'Hiding the truth, lying, and dissembling.' },
  { name: 'History', ability: 'INT', description: 'Historical events, figures, and kingdoms.' },
  { name: 'Insight', ability: 'WIS', description: 'Reading body language and true intentions.' },
  { name: 'Intimidation', ability: 'CHA', description: 'Overt threats, hostility, and coercion.' },
  { name: 'Investigation', ability: 'INT', description: 'Finding clues and deducing secrets.' },
  { name: 'Medicine', ability: 'WIS', description: 'Stabilizing allies and diagnosing illnesses.' },
  { name: 'Nature', ability: 'INT', description: 'Terrain, flora, fauna, and weather.' },
  { name: 'Perception', ability: 'WIS', description: 'Noticing hidden creatures and danger.' },
  { name: 'Performance', ability: 'CHA', description: 'Delighting an audience with art or music.' },
  { name: 'Persuasion', ability: 'CHA', description: 'Diplomacy, charm, and social grace.' },
  { name: 'Religion', ability: 'INT', description: 'Deities, rituals, prayers, and holy lore.' },
  { name: 'Sleight of Hand', ability: 'DEX', description: 'Pickpocketing and manual concealment.' },
  { name: 'Stealth', ability: 'DEX', description: 'Concealment and moving silently.' },
  { name: 'Survival', ability: 'WIS', description: 'Tracking, foraging, and navigating the wild.' },
];

export const CLASS_SKILL_MAP: Record<string, ClassSkillRules> = {
  Barbarian: {
    allowed: ['Animal Handling', 'Athletics', 'Intimidation', 'Nature', 'Perception', 'Survival'],
    recommended: ['Athletics', 'Perception'],
    count: 2,
  },
  Bard: {
    allowed: ALL_DND_SKILLS.map((s) => s.name),
    recommended: ['Deception', 'Performance', 'Persuasion'],
    count: 3,
  },
  Cleric: {
    allowed: ['History', 'Insight', 'Medicine', 'Persuasion', 'Religion'],
    recommended: ['Insight', 'Religion'],
    count: 2,
  },
  Druid: {
    allowed: ['Arcana', 'Animal Handling', 'Insight', 'Medicine', 'Nature', 'Perception', 'Religion', 'Survival'],
    recommended: ['Nature', 'Perception'],
    count: 2,
  },
  Fighter: {
    allowed: ['Acrobatics', 'Animal Handling', 'Athletics', 'History', 'Insight', 'Intimidation', 'Perception', 'Survival'],
    recommended: ['Athletics', 'Perception'],
    count: 2,
  },
  Monk: {
    allowed: ['Acrobatics', 'Athletics', 'History', 'Insight', 'Religion', 'Stealth'],
    recommended: ['Acrobatics', 'Stealth'],
    count: 2,
  },
  Paladin: {
    allowed: ['Athletics', 'Insight', 'Intimidation', 'Medicine', 'Persuasion', 'Religion'],
    recommended: ['Athletics', 'Persuasion'],
    count: 2,
  },
  Ranger: {
    allowed: ['Animal Handling', 'Athletics', 'Insight', 'Investigation', 'Nature', 'Perception', 'Stealth', 'Survival'],
    recommended: ['Perception', 'Stealth', 'Survival'],
    count: 3,
  },
  Rogue: {
    allowed: [
      'Acrobatics',
      'Athletics',
      'Deception',
      'Insight',
      'Intimidation',
      'Investigation',
      'Perception',
      'Performance',
      'Persuasion',
      'Sleight of Hand',
      'Stealth',
    ],
    recommended: ['Stealth', 'Sleight of Hand', 'Perception', 'Acrobatics'],
    count: 4,
  },
  Sorcerer: {
    allowed: ['Arcana', 'Deception', 'Insight', 'Intimidation', 'Persuasion', 'Religion'],
    recommended: ['Arcana', 'Persuasion'],
    count: 2,
  },
  Warlock: {
    allowed: ['Arcana', 'Deception', 'History', 'Intimidation', 'Investigation', 'Nature', 'Religion'],
    recommended: ['Arcana', 'Deception'],
    count: 2,
  },
  Wizard: {
    allowed: ['Arcana', 'History', 'Insight', 'Investigation', 'Medicine', 'Religion'],
    recommended: ['Arcana', 'Investigation'],
    count: 2,
  },
  Artificer: {
    allowed: ['Arcana', 'History', 'Investigation', 'Medicine', 'Nature', 'Perception', 'Sleight of Hand'],
    recommended: ['Arcana', 'Investigation'],
    count: 2,
  },
};

export function getClassSkillRules(className: string): ClassSkillRules {
  const norm = Object.keys(CLASS_SKILL_MAP).find((c) => c.toLowerCase() === (className || '').toLowerCase());
  return norm
    ? CLASS_SKILL_MAP[norm]
    : { allowed: ALL_DND_SKILLS.map((s) => s.name), recommended: ['Athletics', 'Perception'], count: 2 };
}

export function isSpellcasterClass(
  className: string,
  subclass?: string | null,
  level: number = 1,
  is2024: boolean = false
): boolean {
  const c = (className || '').toLowerCase();
  const sub = (subclass || '').toLowerCase();

  // Full casters & Artificer
  if (['bard', 'cleric', 'druid', 'sorcerer', 'warlock', 'wizard', 'artificer'].includes(c)) {
    return true;
  }

  // Half casters
  if (['paladin', 'ranger'].includes(c)) {
    return is2024 ? true : level >= 2;
  }

  // Third casters
  if (c === 'fighter' && sub.includes('eldritch knight') && level >= 3) {
    return true;
  }
  if (c === 'rogue' && sub.includes('arcane trickster') && level >= 3) {
    return true;
  }

  return false;
}

export const CLASS_SUGGESTED_FEATS: Record<string, string[]> = {
  Barbarian: ['Great Weapon Master', 'Polearm Master', 'Sentinel', 'Tough', 'Alert', 'Savage Attacker'],
  Fighter: ['Great Weapon Master', 'Polearm Master', 'Sharpshooter', 'Crossbow Expert', 'Heavy Armor Master', 'Sentinel', 'Alert', 'Tough'],
  Paladin: ['War Caster', 'Polearm Master', 'Great Weapon Master', 'Heavy Armor Master', 'Sentinel', 'Alert', 'Tough'],
  Cleric: ['War Caster', 'Resilient', 'Alert', 'Magic Initiate', 'Telekinetic', 'Tough'],
  Druid: ['War Caster', 'Resilient', 'Alert', 'Telepathic', 'Tough', 'Observant'],
  Wizard: ['War Caster', 'Resilient', 'Alert', 'Telekinetic', 'Fey Touched', 'Lucky'],
  Sorcerer: ['War Caster', 'Fey Touched', 'Alert', 'Metamagic Adept', 'Lucky', 'Telekinetic'],
  Warlock: ['War Caster', 'Fey Touched', 'Shadow Touched', 'Alert', 'Spell Sniper', 'Lucky'],
  Bard: ['Inspiring Leader', 'War Caster', 'Fey Touched', 'Musician', 'Alert', 'Lucky'],
  Ranger: ['Sharpshooter', 'Crossbow Expert', 'Alert', 'Mobile', 'Skilled', 'Tough'],
  Rogue: ['Alert', 'Skilled', 'Mobile', 'Sharpshooter', 'Crossbow Expert', 'Lucky', 'Observant'],
  Monk: ['Mobile', 'Alert', 'Tough', 'Crusher', 'Observant'],
  Artificer: ['War Caster', 'Sharpshooter', 'Alert', 'Tough'],
};

export const ORIGIN_SUGGESTED_FEATS = ['Alert', 'Tough', 'Magic Initiate', 'Lucky', 'Musician', 'Savage Attacker', 'Skilled', 'Healer'];

export function getRecommendedFeats(className: string, level: number = 1, is2024: boolean = false): string[] {
  const norm = Object.keys(CLASS_SUGGESTED_FEATS).find((c) => c.toLowerCase() === (className || '').toLowerCase());
  const classSpecific = norm ? CLASS_SUGGESTED_FEATS[norm] : ['Alert', 'Tough', 'Lucky'];

  if (level < 4 && is2024) {
    // Level 1-3 origin feats
    return ORIGIN_SUGGESTED_FEATS.filter((f) => classSpecific.includes(f) || ['Alert', 'Tough', 'Lucky'].includes(f));
  }

  return classSpecific;
}

export const CLASS_SUGGESTED_SPELLS: Record<string, string[]> = {
  Wizard: [
    'Fire Bolt', 'Ray of Frost', 'Mage Hand', 'Minor Illusion', 'Prestidigitation',
    'Shield', 'Mage Armor', 'Magic Missile', 'Find Familiar', 'Absorb Elements', 'Detect Magic',
    'Misty Step', 'Mirror Image', 'Web', 'Scorching Ray', 'Hold Person',
    'Fireball', 'Counterspell', 'Haste', 'Fly', 'Hypnotic Pattern',
    'Dimension Door', 'Polymorph', 'Greater Invisibility',
    'Wall of Force', 'Synaptic Static'
  ],
  Cleric: [
    'Sacred Flame', 'Guidance', 'Toll the Dead', 'Thaumaturgy', 'Light',
    'Bless', 'Healing Word', 'Guiding Bolt', 'Sanctuary', 'Cure Wounds',
    'Spiritual Weapon', 'Hold Person', 'Aid', 'Lesser Restoration', 'Silence',
    'Spirit Guardians', 'Revivify', 'Dispel Magic', 'Mass Healing Word',
    'Banishment', 'Death Ward',
    'Flame Strike', 'Greater Restoration', 'Mass Cure Wounds'
  ],
  Warlock: [
    'Eldritch Blast', 'Mage Hand', 'Prestidigitation', 'Minor Illusion',
    'Hex', 'Armor of Agathys', 'Hellish Rebuke', 'Witch Bolt',
    'Misty Step', 'Darkness', 'Invisibility', 'Hold Person',
    'Hunger of Hadar', 'Hypnotic Pattern', 'Counterspell', 'Fly',
    'Dimension Door', 'Banishment',
    'Synaptic Static', 'Hold Monster'
  ],
  Sorcerer: [
    'Fire Bolt', 'Shocking Grasp', 'Light', 'Prestidigitation', 'Ray of Frost',
    'Shield', 'Magic Missile', 'Chaos Bolt', 'Mage Armor', 'Absorb Elements',
    'Misty Step', 'Scorching Ray', 'Mirror Image', 'Hold Person',
    'Fireball', 'Counterspell', 'Haste', 'Lightning Bolt',
    'Greater Invisibility', 'Polymorph', 'Dimension Door',
    'Synaptic Static', 'Wall of Stone'
  ],
  Druid: [
    'Shillelagh', 'Thorn Whip', 'Druidcraft', 'Guidance', 'Produce Flame',
    'Entangle', 'Cure Wounds', 'Goodberry', 'Faerie Fire', 'Healing Word',
    'Moonbeam', 'Spike Growth', 'Pass without Trace', 'Barkskin',
    'Call Lightning', 'Revivify', 'Dispel Magic', 'Plant Growth',
    'Polymorph', 'Confusion',
    'Wall of Stone', 'Greater Restoration'
  ],
  Bard: [
    'Vicious Mockery', 'Minor Illusion', 'Mage Hand', 'Prestidigitation',
    'Healing Word', 'Dissonant Whispers', 'Faerie Fire', 'Tasha\'s Hideous Laughter', 'Bane',
    'Invisibility', 'Heat Metal', 'Shatter', 'Hold Person', 'Suggestion',
    'Hypnotic Pattern', 'Dispel Magic', 'Major Image',
    'Dimension Door', 'Polymorph',
    'Synaptic Static', 'Greater Restoration'
  ],
  Paladin: [
    'Bless', 'Thunderous Smite', 'Compelled Duel', 'Wrathful Smite', 'Cure Wounds',
    'Aid', 'Find Steed', 'Lesser Restoration', 'Misty Step',
    'Revivify', 'Dispel Magic', 'Crusader\'s Mantle',
    'Death Ward', 'Find Greater Steed',
    'Holy Weapon', 'Destructive Wave'
  ],
  Ranger: [
    'Hunter\'s Mark', 'Cure Wounds', 'Zephyr Strike', 'Ensnaring Strike', 'Goodberry',
    'Pass without Trace', 'Spike Growth', 'Lesser Restoration', 'Silence',
    'Conjure Animals', 'Lightning Arrow', 'Revivify',
    'Freedom of Movement', 'Grasping Vine',
    'Swift Quiver', 'Commune with Nature'
  ],
  Artificer: [
    'Fire Bolt', 'Mending', 'Guidance', 'Shocking Grasp',
    'Cure Wounds', 'Shield', 'Faerie Fire', 'Absorb Elements', 'Catapult',
    'Aid', 'Invisibility', 'Web', 'Heat Metal', 'Lesser Restoration',
    'Revivify', 'Dispel Magic', 'Haste'
  ]
};

export function getRecommendedSpells(className: string): string[] {
  const norm = Object.keys(CLASS_SUGGESTED_SPELLS).find((c) => c.toLowerCase() === (className || '').toLowerCase());
  return norm ? CLASS_SUGGESTED_SPELLS[norm] : [];
}
