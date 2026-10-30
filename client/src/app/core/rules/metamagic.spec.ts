import { CharacterSchema, FeatureTrait } from '../models/character.model';
import {
  knownMetamagic,
  metamagicCost,
  metamagicKnownLimit,
  metamagicOptions,
  spendMetamagic,
  toggleMetamagicFeature,
} from './index';

function sorcerer(level: number, features: FeatureTrait[] = [], points = 5): CharacterSchema {
  return {
    char_class: 'Sorcerer',
    char_level: level,
    classes: [{ class_name: 'Sorcerer', level }],
    features_traits: features,
    class_resources: [{ name: 'Sorcery Points', current: points, max: level, recharge: 'long', auto: true }],
  } as unknown as CharacterSchema;
}

const byId = (edition: '2014' | '2024', id: string) => metamagicOptions(edition).find((o) => o.id === id)!;

describe('metamagic', () => {
  it('prices options by edition, with 2014 Twinned paying the spell level', () => {
    expect(byId('2014', 'heightened').cost).toBe(3);
    expect(byId('2024', 'heightened').cost).toBe(2);
    const twin14 = byId('2014', 'twinned');
    expect([0, 1, 3].map((lvl) => metamagicCost(twin14, lvl))).toEqual([1, 1, 3]);
    expect(metamagicCost(byId('2024', 'twinned'), 3)).toBe(1);
  });

  it('knows how many options the class grants, plus Metamagic Adept', () => {
    expect([2, 3, 10, 17].map((l) => metamagicKnownLimit(sorcerer(l), '2014'))).toEqual([0, 2, 3, 4]);
    expect([2, 10, 17].map((l) => metamagicKnownLimit(sorcerer(l), '2024'))).toEqual([2, 4, 6]);
    const adept = sorcerer(3, [{ name: 'Metamagic Adept', description: 'You learn two Metamagic options.' }]);
    expect(metamagicKnownLimit(adept, '2014')).toBe(4);
  });

  it('reads known options from the sheet, not from the class feature that describes them all', () => {
    const options = metamagicOptions('2014');
    const sheet = sorcerer(8, [
      { name: 'Metamagic (Quickened, Subtle)', description: '' },
      { name: 'Twinned Spell', description: 'A second target.' },
      {
        name: 'Metamagic',
        description:
          'Careful Spell, Distant Spell, Empowered Spell, Extended Spell, Heightened Spell, Quickened Spell, Subtle Spell, Twinned Spell',
      },
    ]);
    expect([...knownMetamagic(sheet, options)].sort()).toEqual(['quickened', 'subtle', 'twinned']);
  });

  it('adds and removes its own feature when an option is toggled', () => {
    const quickened = byId('2024', 'quickened');
    const added = toggleMetamagicFeature([], quickened);
    expect(added).toEqual([{ name: 'Metamagic: Quickened Spell', description: quickened.summary, source: 'Sorcerer (Metamagic)' }]);
    expect(toggleMetamagicFeature(added, quickened)).toEqual([]);
  });

  it('spends sorcery points, and refuses when the pool cannot pay', () => {
    const quickened = byId('2014', 'quickened');
    expect(spendMetamagic(sorcerer(8, [], 5), quickened)![0].current).toBe(3);
    expect(spendMetamagic(sorcerer(8, [], 1), quickened)).toBeNull();
    expect(spendMetamagic(sorcerer(8, [], 5), byId('2014', 'twinned'), 4)![0].current).toBe(1);
  });
});
