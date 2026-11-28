import type { CharacterSchema } from '../models/character.model';
import {
  buildDamageDefensePills,
  computeAdjustedDamage,
  describeConditionImpact,
  detectConditionWarnings,
  effectiveSpeed,
  evaluateConditionEffects,
  getConditionCountermeasures,
  hasConditionAdvantage,
  hasConditionDisadvantage,
  inferDamageMitigation,
  isAutoFailSave,
  resolveRollMode,
  speedLockReason,
} from './index';

function hero(overrides: Partial<CharacterSchema> = {}): CharacterSchema {
  return {
    char_name: 'Kaelen',
    char_class: 'Fighter',
    char_level: 5,
    armor_class: 16,
    hp_max: 44,
    speed: 30,
    base_speed: 30,
    proficiency_bonus: 3,
    race: 'Human',
    background: 'Soldier',
    dnd_edition: '2014 Edition',
    stats: { STR: 16, DEX: 14, CON: 14, INT: 10, WIS: 12, CHA: 10 },
    conditions: [],
    features_traits: [],
    senses: [],
    ...overrides,
  };
}

describe('Conditions, Countermeasures (Antidotes) & Damage Mitigation Rules (#275)', () => {
  it.each(['2014 Edition', '2024 Revision (5.5e)'])(
    'evaluates roll penalties, auto-fails, and non-destructive speed lock in %s',
    (edition) => {
      const is2024 = edition.includes('2024');

      const poisoned = hero({ dnd_edition: edition, conditions: ['Poisoned'] });
      expect(hasConditionDisadvantage(poisoned, 'attack')).toBe(true);
      expect(hasConditionDisadvantage(poisoned, 'check', 'STR')).toBe(true);
      expect(hasConditionDisadvantage(poisoned, 'save', 'CON')).toBe(false);
      // 5e Adv/Dis cancellation via resolveRollMode
      expect(resolveRollMode('advantage', hasConditionDisadvantage(poisoned, 'attack'))).toEqual({
        mode: 'normal',
        cancelled: true,
      });

      const restrained = hero({ dnd_edition: edition, conditions: ['Restrained'] });
      expect(hasConditionDisadvantage(restrained, 'attack')).toBe(true);
      expect(hasConditionDisadvantage(restrained, 'save', 'DEX')).toBe(true);
      expect(hasConditionDisadvantage(restrained, 'save', 'STR')).toBe(false);
      expect(effectiveSpeed(restrained)).toBe(0);
      expect(speedLockReason(restrained)).toBe('Restrained');

      const unrestrained = hero({ ...restrained, conditions: [], speed: 0, base_speed: 35 });
      expect(effectiveSpeed(unrestrained)).toBe(35);
      expect(speedLockReason(unrestrained)).toBeNull();

      const paralyzed = hero({ dnd_edition: edition, conditions: ['Paralyzed'] });
      expect(isAutoFailSave(paralyzed, 'STR')).toBe(true);
      expect(isAutoFailSave(paralyzed, 'DEX')).toBe(true);
      expect(isAutoFailSave(paralyzed, 'WIS')).toBe(false);
      expect(effectiveSpeed(paralyzed)).toBe(0);

      const invisible = hero({ dnd_edition: edition, conditions: ['Invisible'] });
      expect(hasConditionAdvantage(invisible, 'attack')).toBe(true);
      expect(hasConditionAdvantage(invisible, 'initiative')).toBe(is2024);

      const both = evaluateConditionEffects(
        hero({ dnd_edition: edition, conditions: ['Invisible', 'Poisoned'] })
      );
      expect(
        resolveRollMode(
          'normal',
          both.roll.attack.hasDisadvantage,
          both.roll.attack.hasAdvantage
        )
      ).toEqual({ mode: 'normal', cancelled: true });

      const prone = hero({ dnd_edition: edition, conditions: ['Prone'] });
      expect(effectiveSpeed(prone)).toBe(30);
      expect(hasConditionDisadvantage(prone, 'attack')).toBe(true);
    }
  );

  it('detects 2014 vs 2024 class, species, and sense countermeasures cleanly', () => {
    const paladinBerserker = hero({
      dnd_edition: '2024 Revision (5.5e)',
      race: 'Elf',
      char_class: 'Paladin',
      char_level: 10,
      subclass: 'Oath of Devotion',
      classes: [{ class_name: 'Paladin', level: 10, subclass: 'Oath of Devotion' }],
      features_traits: [
        { name: 'Mindless Rage', description: 'Immune to Charmed and Frightened while Raging.' },
        { name: 'Blind Fighting', description: 'Blindsight 10 ft.' },
      ],
    });
    const cm = getConditionCountermeasures(paladinBerserker);
    expect(cm.some((c) => c.condition === 'Frightened' && c.source === 'Aura of Courage')).toBe(true);
    expect(cm.some((c) => c.condition === 'Charmed' && c.source === 'Aura of Devotion')).toBe(true);
    expect(cm.some((c) => c.condition === 'Charmed' && c.source === 'Fey Ancestry')).toBe(true);
    expect(cm.some((c) => c.condition === 'Blinded' && c.kind === 'sense_mitigation')).toBe(true);

    const warnings = detectConditionWarnings(paladinBerserker, ['Frightened', 'Prone']);
    expect(warnings.every((w) => w.condition === 'Frightened')).toBe(true);
    expect(warnings.length).toBeGreaterThanOrEqual(2);

    // 2014 vs 2024 Monk countermeasures
    const monk14 = hero({
      dnd_edition: '2014 Edition',
      char_class: 'Monk',
      char_level: 10,
      classes: [{ class_name: 'Monk', level: 10 }],
    });
    expect(
      getConditionCountermeasures(monk14).some(
        (c) => c.condition === 'Poisoned' && c.source === 'Purity of Body' && c.kind === 'immune'
      )
    ).toBe(true);

    const monk24 = hero({
      dnd_edition: '2024 Revision (5.5e)',
      char_class: 'Monk',
      char_level: 10,
      classes: [{ class_name: 'Monk', level: 10 }],
    });
    expect(
      getConditionCountermeasures(monk24).some(
        (c) => c.condition === 'Poisoned' && c.source === 'Self-Restoration' && c.kind === 'action_end'
      )
    ).toBe(true);
    expect(
      getConditionCountermeasures(monk24).some((c) => c.source === 'Purity of Body')
    ).toBe(false);

    // Halfling Brave / Stout Resilience, Dwarf Dwarven Resilience, 2024 Land Druid Nature's Ward
    const halfling = hero({ race: 'Stout Halfling' });
    expect(getConditionCountermeasures(halfling).some((c) => c.condition === 'Frightened' && c.source === 'Brave')).toBe(true);
    expect(getConditionCountermeasures(halfling).some((c) => c.condition === 'Poisoned' && c.source === 'Stout Resilience')).toBe(true);

    const druid24 = hero({
      dnd_edition: '2024 Revision (5.5e)',
      char_class: 'Druid',
      subclass: 'Circle of the Land',
      char_level: 10,
      classes: [{ class_name: 'Druid', level: 10, subclass: 'Circle of the Land' }],
    });
    expect(
      getConditionCountermeasures(druid24).some((c) => c.condition === 'Poisoned' && c.source === "Nature's Ward")
    ).toBe(true);

    // 2024 Incapacitated -> Initiative Disadvantage
    expect(
      hasConditionDisadvantage(
        hero({ dnd_edition: '2024 Revision (5.5e)', conditions: ['Incapacitated'] }),
        'initiative'
      )
    ).toBe(true);
    expect(
      hasConditionDisadvantage(hero({ dnd_edition: '2014 Edition', conditions: ['Incapacitated'] }), 'initiative')
    ).toBe(false);

    // Poisoned & Frightened -> Initiative Disadvantage in both 2014 & 2024 (Dexterity ability check)
    expect(
      hasConditionDisadvantage(hero({ dnd_edition: '2014 Edition', conditions: ['Poisoned'] }), 'initiative')
    ).toBe(true);
    expect(
      hasConditionDisadvantage(hero({ dnd_edition: '2024 Revision (5.5e)', conditions: ['Frightened'] }), 'initiative')
    ).toBe(true);

    const dwarf = hero({ dnd_edition: '2024 Revision (5.5e)', race: 'Dwarf' });
    expect(getConditionCountermeasures(dwarf).some((c) => c.condition === 'Poisoned' && c.source === 'Dwarven Resilience')).toBe(true);
  });

  it('computes 5e floor half resistance, double vulnerability, zero immunity, and defense pills', () => {
    expect(computeAdjustedDamage(25, 'raw')).toBe(25);
    expect(computeAdjustedDamage(25, 'resist')).toBe(12);
    expect(computeAdjustedDamage(1, 'resist')).toBe(0);
    expect(computeAdjustedDamage(17, 'vuln')).toBe(34);
    expect(computeAdjustedDamage(99, 'immune')).toBe(0);

    expect(inferDamageMitigation('Fire', ['Fire', 'Cold'], ['Poison'], ['Radiant'])).toBe('resist');
    expect(inferDamageMitigation('Poison', ['Poison'], ['Poison'], [])).toBe('immune');
    expect(inferDamageMitigation('Radiant', ['Radiant'], [], ['Radiant'])).toBe('vuln');
    expect(inferDamageMitigation('Slashing', ['Fire'], ['Poison'], ['Radiant'])).toBe('raw');

    const pills = buildDamageDefensePills(['Fire', 'Poison'], ['Poison'], ['Cold']);
    expect(pills).toEqual([
      { label: 'Poison', mode: 'immune' },
      { label: 'Cold', mode: 'vuln' },
      { label: 'Fire', mode: 'resist' },
    ]);
    expect(buildDamageDefensePills(['Fire'], [], ['Fire'])).toEqual([
      { label: 'Fire', mode: 'vuln' },
      { label: 'Fire', mode: 'resist' },
    ]);

    expect(describeConditionImpact('Invisible', hero({ dnd_edition: '2024 Revision (5.5e)' }))).toContain(
      'ADV Init (2024)'
    );
    expect(describeConditionImpact('Incapacitated', hero({ dnd_edition: '2024 Revision (5.5e)' }))).toContain(
      'DIS Init (2024)'
    );
    expect(describeConditionImpact('Petrified', hero({ dnd_edition: '2014 Edition' }))).toContain(
      'Resist All Damage'
    );
    expect(describeConditionImpact('Stunned', hero({ dnd_edition: '2014 Edition' }))).toContain('Speed 0 ft');
    expect(describeConditionImpact('Stunned', hero({ dnd_edition: '2024 Revision (5.5e)' }))).not.toContain(
      'Speed 0 ft'
    );
    expect(effectiveSpeed(hero({ dnd_edition: '2024 Revision (5.5e)', conditions: ['Stunned'], speed: 30 }))).toBe(30);
    expect(effectiveSpeed(hero({ dnd_edition: '2014 Edition', conditions: ['Stunned'], speed: 30 }))).toBe(0);
    expect(describeConditionImpact('Invisible', hero({ dnd_edition: '2014 Edition' }))).not.toContain(
      'ADV Init (2024)'
    );
  });
});
