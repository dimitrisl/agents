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

// --- Maximum Capacity Limits ---

export function getMaxOriginFeats(race: string, edition: string = '2014'): number {
  const is2024 = (edition || '').includes('2024');
  if (is2024) {
    return (race || '').toLowerCase() === 'human' ? 2 : 1;
  }
  return (race || '').toLowerCase() === 'variant human' ? 1 : 0;
}

export function getMaxGeneralFeats(className: string, level: number = 1): number {
  const c = (className || '').toLowerCase();
  let milestones = [4, 8, 12, 16, 19];
  if (c === 'fighter') milestones = [4, 6, 8, 12, 14, 16, 19];
  else if (c === 'rogue') milestones = [4, 8, 10, 12, 16, 19];
  return milestones.filter((m) => m <= level).length;
}

export function getMaxCantrips(className: string, level: number = 1): number {
  const c = (className || '').toLowerCase();
  if (['wizard', 'cleric'].includes(c)) return level < 4 ? 3 : level < 10 ? 4 : 5;
  if (['sorcerer'].includes(c)) return level < 4 ? 4 : level < 10 ? 5 : 6;
  if (['druid', 'bard', 'warlock'].includes(c)) return level < 4 ? 2 : level < 10 ? 3 : 4;
  if (['artificer'].includes(c)) return level < 10 ? 2 : level < 14 ? 3 : 4;
  return 0;
}

export function getMaxPreparedSpells(
  className: string,
  level: number = 1,
  abilityMod: number = 0,
  is2024: boolean = false
): number {
  const c = (className || '').toLowerCase();
  const idx = Math.min(19, Math.max(0, level - 1));

  if (is2024) {
    const fullCaster = [4, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16, 16, 17, 17, 18, 18, 19, 20, 21, 22];
    const warlock = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 11, 11, 12, 12, 13, 13, 14, 14, 15, 15];
    const halfCaster = [2, 3, 4, 5, 6, 6, 7, 7, 9, 9, 10, 10, 11, 11, 12, 12, 14, 14, 15, 15];

    if (['wizard', 'cleric', 'druid', 'bard', 'sorcerer'].includes(c)) return fullCaster[idx];
    if (c === 'warlock') return warlock[idx];
    if (['paladin', 'ranger'].includes(c)) return halfCaster[idx];
    return 0;
  } else {
    // 2014 rules
    if (['wizard', 'cleric', 'druid'].includes(c)) return Math.max(1, level + abilityMod);
    if (c === 'paladin') return level >= 2 ? Math.max(1, Math.floor(level / 2) + abilityMod) : 0;
    if (c === 'artificer') return Math.max(1, Math.floor(level / 2) + abilityMod);

    const bard = [4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 15, 16, 18, 19, 19, 20, 22, 22, 22];
    const sorcerer = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 12, 13, 13, 14, 14, 15, 15, 15, 15];
    const warlock = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 11, 11, 12, 12, 13, 13, 14, 14, 15, 15];
    const ranger = [0, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11];

    if (c === 'bard') return bard[idx];
    if (c === 'sorcerer') return sorcerer[idx];
    if (c === 'warlock') return warlock[idx];
    if (c === 'ranger') return ranger[idx];
    return 0;
  }
}

export const BACKGROUND_SKILLS_MAP: Record<string, string[]> = {
  Acolyte: ['Insight', 'Religion'],
  Artisan: ['Investigation', 'Persuasion'],
  'Guild Artisan': ['Insight', 'Persuasion'],
  Charlatan: ['Deception', 'Sleight of Hand'],
  Criminal: ['Deception', 'Stealth'],
  Entertainer: ['Acrobatics', 'Performance'],
  Farmer: ['Animal Handling', 'Nature'],
  'Folk Hero': ['Animal Handling', 'Survival'],
  Guard: ['Athletics', 'Perception'],
  Guide: ['Stealth', 'Survival'],
  Hermit: ['Medicine', 'Religion'],
  Merchant: ['Animal Handling', 'Persuasion'],
  Noble: ['History', 'Persuasion'],
  Outlander: ['Athletics', 'Survival'],
  Sage: ['Arcana', 'History'],
  Sailor: ['Athletics', 'Perception'],
  Scribe: ['Investigation', 'Perception'],
  Soldier: ['Athletics', 'Intimidation'],
  Urchin: ['Sleight of Hand', 'Stealth'],
  Wayfarer: ['Insight', 'Stealth'],
};

export function getBackgroundSkills(background: string): string[] {
  const norm = Object.keys(BACKGROUND_SKILLS_MAP).find(
    (b) => b.toLowerCase() === (background || '').toLowerCase()
  );
  return norm ? BACKGROUND_SKILLS_MAP[norm] : [];
}

export function getMaxCastableSpellLevel(
  className: string,
  level: number = 1,
  is2024: boolean = false,
  subclass?: string | null
): number {
  const c = (className || '').toLowerCase();
  const lvl = Math.max(1, level);

  if (!isSpellcasterClass(className, subclass, level, is2024)) {
    return 0;
  }

  // Full casters
  if (['wizard', 'cleric', 'druid', 'bard', 'sorcerer'].includes(c)) {
    return Math.min(9, Math.ceil(lvl / 2));
  }

  // Warlock (Pact Magic)
  if (c === 'warlock') {
    return Math.min(5, Math.ceil(lvl / 2));
  }

  // Half casters
  if (['paladin', 'ranger'].includes(c)) {
    if (!is2024 && lvl < 2) return 0;
    return Math.min(5, Math.ceil(lvl / 4));
  }

  // Artificer
  if (c === 'artificer') {
    return Math.min(5, Math.ceil(lvl / 4));
  }

  // Third casters
  if (lvl < 3) return 0;
  return Math.min(4, Math.ceil((lvl - 2) / 6));
}
