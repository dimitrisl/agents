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
});
