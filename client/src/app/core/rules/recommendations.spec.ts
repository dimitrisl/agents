import {
  getClassSkillRules,
  isSpellcasterClass,
  getRecommendedFeats,
  getRecommendedSpells,
  ALL_DND_SKILLS,
} from './recommendations';

describe('Manual Build Recommendations Rules', () => {
  it('should return correct skill rules and counts for standard classes', () => {
    const fighter = getClassSkillRules('Fighter');
    expect(fighter.count).toBe(2);
    expect(fighter.allowed).toContain('Athletics');
    expect(fighter.recommended).toEqual(['Athletics', 'Perception']);

    const rogue = getClassSkillRules('Rogue');
    expect(rogue.count).toBe(4);
    expect(rogue.recommended).toContain('Stealth');

    const bard = getClassSkillRules('Bard');
    expect(bard.count).toBe(3);
    expect(bard.allowed.length).toBe(ALL_DND_SKILLS.length);
  });

  it('should accurately identify spellcasters', () => {
    expect(isSpellcasterClass('Wizard')).toBe(true);
    expect(isSpellcasterClass('Cleric')).toBe(true);
    expect(isSpellcasterClass('Bard')).toBe(true);
    expect(isSpellcasterClass('Barbarian')).toBe(false);
    expect(isSpellcasterClass('Fighter')).toBe(false);
    expect(isSpellcasterClass('Fighter', 'Eldritch Knight', 3)).toBe(true);
    expect(isSpellcasterClass('Fighter', 'Champion', 3)).toBe(false);
    expect(isSpellcasterClass('Paladin', null, 1, false)).toBe(false);
    expect(isSpellcasterClass('Paladin', null, 2, false)).toBe(true);
    expect(isSpellcasterClass('Paladin', null, 1, true)).toBe(true);
  });

  it('should return recommended feats per class and level', () => {
    const clericFeats = getRecommendedFeats('Cleric', 4);
    expect(clericFeats).toContain('War Caster');

    const barbarianFeats = getRecommendedFeats('Barbarian', 4);
    expect(barbarianFeats).toContain('Great Weapon Master');

    const originFeats = getRecommendedFeats('Wizard', 1, true);
    expect(originFeats).toContain('Alert');
  });

  it('should return recommended spells per class', () => {
    const wizardSpells = getRecommendedSpells('Wizard');
    expect(wizardSpells).toContain('Fire Bolt');
    expect(wizardSpells).toContain('Shield');
    expect(wizardSpells).toContain('Fireball');

    const clericSpells = getRecommendedSpells('Cleric');
    expect(clericSpells).toContain('Sacred Flame');
    expect(clericSpells).toContain('Bless');
    expect(clericSpells).toContain('Spirit Guardians');
  });

  it('should calculate max origin and general feats capacity', () => {
    const { getMaxOriginFeats, getMaxGeneralFeats } = require('./recommendations');

    // 2024: 1 Origin Feat, or 2 for Human
    expect(getMaxOriginFeats('Human', '2024')).toBe(2);
    expect(getMaxOriginFeats('Elf', '2024')).toBe(1);
    expect(getMaxOriginFeats('Human', '2014')).toBe(0);
    expect(getMaxOriginFeats('Variant Human', '2014')).toBe(1);

    // General feats by level
    expect(getMaxGeneralFeats('Wizard', 1)).toBe(0);
    expect(getMaxGeneralFeats('Wizard', 4)).toBe(1);
    expect(getMaxGeneralFeats('Wizard', 8)).toBe(2);

    // Fighter extra milestones at 6 and 14
    expect(getMaxGeneralFeats('Fighter', 4)).toBe(1);
    expect(getMaxGeneralFeats('Fighter', 6)).toBe(2);
    expect(getMaxGeneralFeats('Fighter', 8)).toBe(3);
    expect(getMaxGeneralFeats('Fighter', 14)).toBe(5);

    // Rogue extra milestone at 10
    expect(getMaxGeneralFeats('Rogue', 10)).toBe(3);
  });

  it('should calculate max cantrips and prepared spells capacity', () => {
    const { getMaxCantrips, getMaxPreparedSpells } = require('./recommendations');

    // Cantrips
    expect(getMaxCantrips('Wizard', 1)).toBe(3);
    expect(getMaxCantrips('Wizard', 4)).toBe(4);
    expect(getMaxCantrips('Wizard', 10)).toBe(5);
    expect(getMaxCantrips('Fighter', 1)).toBe(0);

    // 2024 prepared spells table
    expect(getMaxPreparedSpells('Wizard', 1, 3, true)).toBe(4);
    expect(getMaxPreparedSpells('Wizard', 3, 3, true)).toBe(6);
    expect(getMaxPreparedSpells('Paladin', 1, 3, true)).toBe(2);

    // 2014 prepared spells (level + ability mod)
    expect(getMaxPreparedSpells('Wizard', 1, 3, false)).toBe(4); // 1 + 3
    expect(getMaxPreparedSpells('Wizard', 3, 3, false)).toBe(6); // 3 + 3
  });

  it('should return background skills and max castable spell level correctly', () => {
    const { getBackgroundSkills, getMaxCastableSpellLevel } = require('./recommendations');

    expect(getBackgroundSkills('Soldier')).toEqual(['Athletics', 'Intimidation']);
    expect(getBackgroundSkills('Acolyte')).toEqual(['Insight', 'Religion']);
    expect(getBackgroundSkills('Sailor')).toEqual(['Athletics', 'Perception']);
    expect(getBackgroundSkills('Unknown')).toEqual([]);

    // Full caster spell level progression
    expect(getMaxCastableSpellLevel('Wizard', 1)).toBe(1);
    expect(getMaxCastableSpellLevel('Wizard', 3)).toBe(2);
    expect(getMaxCastableSpellLevel('Wizard', 5)).toBe(3);
    expect(getMaxCastableSpellLevel('Wizard', 17)).toBe(9);

    // Half caster progression
    expect(getMaxCastableSpellLevel('Paladin', 1, true)).toBe(1);
    expect(getMaxCastableSpellLevel('Paladin', 1, false)).toBe(0);
    expect(getMaxCastableSpellLevel('Paladin', 2, false)).toBe(1);
    expect(getMaxCastableSpellLevel('Paladin', 5, true)).toBe(2);

    // Third caster / non caster
    expect(getMaxCastableSpellLevel('Barbarian', 5)).toBe(0);
  });
});
