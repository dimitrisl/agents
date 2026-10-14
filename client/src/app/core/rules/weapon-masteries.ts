export interface WeaponMasteryDefinition {
  name: string;
  summary: string;
  ruleText: string;
  trigger: 'Hit' | 'Miss' | 'Attack Action' | 'Damage';
  hasSaveDc?: boolean;
}

export const WEAPON_MASTERIES: Record<string, WeaponMasteryDefinition> = {
  Cleave: {
    name: 'Cleave',
    summary: 'Make a second melee attack against an adjacent foe.',
    ruleText:
      "If you hit a creature with a melee attack roll using this weapon, you can make a melee attack roll with the weapon against a second creature within 5 feet of the first that is also within your reach. On a hit, the second creature takes the weapon's damage die, excluding your ability modifier.",
    trigger: 'Hit',
  },
  Graze: {
    name: 'Graze',
    summary: 'Deal ability modifier damage on a miss.',
    ruleText:
      "If your attack roll with this weapon misses a creature, you still deal damage to that creature equal to the ability modifier you used to make the attack roll. This damage is of the same type dealt by the weapon, and the damage can't be increased in any way.",
    trigger: 'Miss',
  },
  Nick: {
    name: 'Nick',
    summary: 'Light weapon extra attack becomes part of Attack action.',
    ruleText:
      'When you make the extra attack of the Light weapon property, you can make it as part of the Attack action instead of as a Bonus Action. You can make this extra attack only once per turn.',
    trigger: 'Attack Action',
  },
  Push: {
    name: 'Push',
    summary: 'Push creature up to 10 ft away if Large or smaller.',
    ruleText:
      'If you hit a creature with this weapon, you can push the creature up to 10 feet straight away from you if it is Large or smaller.',
    trigger: 'Hit',
  },
  Sap: {
    name: 'Sap',
    summary: 'Target has Disadvantage on its next attack roll.',
    ruleText:
      'If you hit a creature with this weapon, that creature has Disadvantage on its next attack roll before the start of your next turn.',
    trigger: 'Hit',
  },
  Slow: {
    name: 'Slow',
    summary: 'Reduce target speed by 10 ft until start of your next turn.',
    ruleText:
      "If you hit a creature with this weapon and deal damage, you can reduce its Speed by 10 feet until the start of your next turn. You can't reduce the speed by more than 10 feet per turn.",
    trigger: 'Damage',
  },
  Topple: {
    name: 'Topple',
    summary: 'Knock target Prone on failed Constitution save.',
    ruleText:
      'If you hit a creature with this weapon, you can force the creature to make a Constitution saving throw with a DC equal to 8 + your ability modifier used for the attack roll + your Proficiency Bonus. On a failed save, the creature has the Prone condition if it is Large or smaller.',
    trigger: 'Hit',
    hasSaveDc: true,
  },
  Vex: {
    name: 'Vex',
    summary: 'Gain Advantage on your next attack against this target.',
    ruleText:
      'If you hit a creature with this weapon and deal damage, you have Advantage on your next attack roll against that creature before the end of your next turn.',
    trigger: 'Damage',
  },
};

export function getMasteryDefinition(name: string): WeaponMasteryDefinition | undefined {
  if (!name) return undefined;
  const clean = name.trim();
  const foundKey = Object.keys(WEAPON_MASTERIES).find(
    (k) => k.toLowerCase() === clean.toLowerCase()
  );
  return foundKey ? WEAPON_MASTERIES[foundKey] : undefined;
}

export function calculateToppleDc(abilityMod: number, profBonus: number): number {
  return 8 + abilityMod + profBonus;
}
