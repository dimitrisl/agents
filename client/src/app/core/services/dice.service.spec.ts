import { TestBed } from '@angular/core/testing';
import { DiceService, RollMode, DamagePart } from './dice.service';

describe('DiceService', () => {
  let service: DiceService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(DiceService);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  describe('rollDie', () => {
    it('returns a number between 1 and sides', () => {
      jest.spyOn(Math, 'random').mockReturnValue(0.5);
      expect(service.rollDie(20)).toBe(11);

      jest.spyOn(Math, 'random').mockReturnValue(0);
      expect(service.rollDie(20)).toBe(1);

      jest.spyOn(Math, 'random').mockReturnValue(0.9999);
      expect(service.rollDie(20)).toBe(20);
    });
  });

  describe('roll', () => {
    it('rolls a normal d20', () => {
      jest.spyOn(service, 'rollDie').mockReturnValue(15);
      const result = service.roll({ sides: 20, modifier: 3 });

      expect(result.numDice).toBe(1);
      expect(result.sides).toBe(20);
      expect(result.rolls).toEqual([15]);
      expect(result.raw).toBe(15);
      expect(result.modifier).toBe(3);
      expect(result.total).toBe(18);
      expect(result.mode).toBe('normal');
      expect(result.isNat20).toBe(false);
      expect(result.isNat1).toBe(false);
      expect(result.expression).toBe('1d20 (15) +3');
    });

    it('handles advantage on a d20', () => {
      jest.spyOn(service, 'rollDie').mockReturnValueOnce(5).mockReturnValueOnce(15);
      const result = service.roll({ sides: 20, mode: 'advantage' });

      expect(result.rolls).toEqual([5, 15]);
      expect(result.raw).toBe(15); // Max of 5 and 15
      expect(result.total).toBe(15);
      expect(result.mode).toBe('advantage');
    });

    it('handles disadvantage on a d20', () => {
      jest.spyOn(service, 'rollDie').mockReturnValueOnce(18).mockReturnValueOnce(2);
      const result = service.roll({ sides: 20, mode: 'disadvantage' });

      expect(result.rolls).toEqual([18, 2]);
      expect(result.raw).toBe(2); // Min of 18 and 2
      expect(result.total).toBe(2);
      expect(result.mode).toBe('disadvantage');
    });

    it('ignores advantage/disadvantage for non-d20 rolls', () => {
      jest.spyOn(service, 'rollDie').mockReturnValueOnce(3).mockReturnValueOnce(4);
      const result = service.roll({ sides: 6, numDice: 2, mode: 'advantage' });

      expect(result.rolls).toEqual([3, 4]);
      expect(result.raw).toBe(7); // Sum of 3 and 4, not max
      expect(result.mode).toBe('normal'); // mode dropped
    });

    it('flags a natural 20', () => {
      jest.spyOn(service, 'rollDie').mockReturnValue(20);
      const result = service.roll({ sides: 20 });
      expect(result.isNat20).toBe(true);
      expect(result.isNat1).toBe(false);
    });

    it('flags a natural 1', () => {
      jest.spyOn(service, 'rollDie').mockReturnValue(1);
      const result = service.roll({ sides: 20 });
      expect(result.isNat20).toBe(false);
      expect(result.isNat1).toBe(true);
    });

    it('does not flag 20 on non-d20', () => {
      jest.spyOn(service, 'rollDie').mockReturnValue(20);
      const result = service.roll({ sides: 100 });
      expect(result.isNat20).toBe(false);
    });
  });

  describe('rollD20', () => {
    it('rolls 1d20 with modifier and mode', () => {
      const spy = jest.spyOn(service, 'roll').mockReturnValue({} as any);
      service.rollD20(4, 'advantage');
      expect(spy).toHaveBeenCalledWith({ sides: 20, numDice: 1, modifier: 4, mode: 'advantage' });
    });
    it('defaults to normal mode and 0 mod', () => {
      const spy = jest.spyOn(service, 'roll').mockReturnValue({} as any);
      service.rollD20();
      expect(spy).toHaveBeenCalledWith({ sides: 20, numDice: 1, modifier: 0, mode: 'normal' });
    });
  });

  describe('rollNotation', () => {
    it('parses basic notation and rolls', () => {
      const spy = jest.spyOn(service, 'roll').mockReturnValue({} as any);
      service.rollNotation('2d6+3', 'advantage'); // disadvantage/advantage dropped in roll for 2d6
      expect(spy).toHaveBeenCalledWith({ numDice: 2, sides: 6, modifier: 3, mode: 'advantage' });
    });

    it('handles negative modifiers', () => {
      const spy = jest.spyOn(service, 'roll').mockReturnValue({} as any);
      service.rollNotation('1d8-1');
      expect(spy).toHaveBeenCalledWith({ numDice: 1, sides: 8, modifier: -1, mode: 'normal' });
    });

    it('defaults to 1d20 for invalid notation', () => {
      const spy = jest.spyOn(service, 'roll').mockReturnValue({} as any);
      service.rollNotation('potato', 'disadvantage');
      expect(spy).toHaveBeenCalledWith({ sides: 20, numDice: 1, modifier: 0, mode: 'disadvantage' });
    });

    it('defaults to 1 die if omitted', () => {
      const spy = jest.spyOn(service, 'roll').mockReturnValue({} as any);
      service.rollNotation('d10');
      expect(spy).toHaveBeenCalledWith({ numDice: 1, sides: 10, modifier: 0, mode: 'normal' });
    });
  });

  describe('parseNotation', () => {
    it('parses standard notation', () => {
      expect(service.parseNotation('1d8+4')).toEqual({ numDice: 1, sides: 8, modifier: 4 });
    });

    it('parses notation with spaces and trailing text', () => {
      expect(service.parseNotation(' 2d6 + 1 slashing ')).toEqual({ numDice: 2, sides: 6, modifier: 1 });
    });

    it('parses missing numDice as 1', () => {
      expect(service.parseNotation('d12')).toEqual({ numDice: 1, sides: 12, modifier: 0 });
    });

    it('chains modifiers correctly', () => {
      expect(service.parseNotation('1d10+2-1+4')).toEqual({ numDice: 1, sides: 10, modifier: 5 });
    });

    it('parses flat bonus notation', () => {
      expect(service.parseNotation('+2')).toEqual({ numDice: 0, sides: 0, modifier: 2 });
      expect(service.parseNotation('-1')).toEqual({ numDice: 0, sides: 0, modifier: -1 });
      expect(service.parseNotation('5')).toEqual({ numDice: 0, sides: 0, modifier: 5 });
    });

    it('returns null for empty or completely invalid notation', () => {
      expect(service.parseNotation('')).toBeNull();
      expect(service.parseNotation(null as any)).toBeNull();
      expect(service.parseNotation('invalid')).toBeNull();
    });
  });

  describe('rollDamage', () => {
    it('rolls multiple damage parts', () => {
      jest.spyOn(service, 'rollDie').mockImplementation(sides => sides === 8 ? 5 : 3);

      const parts: DamagePart[] = [
        { label: 'Longsword', notation: '1d8+4' },
        { label: 'Sneak Attack', notation: '2d6' },
        { label: 'Rage', notation: '+2' }
      ];

      const result = service.rollDamage(parts);

      expect(result.parts.length).toBe(3);
      expect(result.total).toBe(9 + 6 + 2); // (5+4) + (3+3) + 2
      expect(result.rolls).toEqual([5, 3, 3]); // flat modifier has no rolls
      expect(result.crit).toBe(false);
      expect(result.expression).toContain('Longsword 1d8 (5) +4');
      expect(result.expression).toContain('Sneak Attack 2d6 (3+3)');
      expect(result.expression).toContain('Rage +2');
    });

    it('doubles dice on crit but not flat modifiers', () => {
      jest.spyOn(service, 'rollDie').mockImplementation(() => 4);

      const parts: DamagePart[] = [
        { label: 'Weapon', notation: '1d8+3' }
      ];

      const result = service.rollDamage(parts, { crit: true });

      expect(result.parts[0].numDice).toBe(2);
      expect(result.parts[0].total).toBe(8 + 3); // (4+4) + 3
      expect(result.crit).toBe(true);
    });

    it('does not double dice for parts with noCrit', () => {
      jest.spyOn(service, 'rollDie').mockImplementation(() => 4);

      const parts: DamagePart[] = [
        { label: 'Weapon', notation: '1d8+3' },
        { label: 'Brutal Critical', notation: '1d8', noCrit: true }
      ];

      const result = service.rollDamage(parts, { crit: true });

      expect(result.parts[0].numDice).toBe(2); // Crit doubled
      expect(result.parts[1].numDice).toBe(1); // noCrit prevents doubling
    });

    it('skips invalid parts', () => {
      jest.spyOn(service, 'rollDie').mockReturnValue(5);
      const parts: DamagePart[] = [
        { label: 'Valid', notation: '1d6' },
        { label: 'Invalid', notation: 'invalid' }
      ];

      const result = service.rollDamage(parts);
      expect(result.parts.length).toBe(1);
      expect(result.parts[0].label).toBe('Valid');
    });
  });

  describe('rollAbilityScore', () => {
    it('rolls 4d6 and drops the lowest', () => {
      // Mock returns 2, 4, 6, 1
      jest.spyOn(service, 'rollDie')
        .mockReturnValueOnce(2)
        .mockReturnValueOnce(4)
        .mockReturnValueOnce(6)
        .mockReturnValueOnce(1);

      // sorted: 1, 2, 4, 6 -> drops 1, sum = 12
      expect(service.rollAbilityScore()).toBe(12);
    });
  });

  describe('rollAbilityScores', () => {
    it('rolls 6 ability scores and sorts descending', () => {
      jest.spyOn(service, 'rollAbilityScore')
        .mockReturnValueOnce(12)
        .mockReturnValueOnce(18)
        .mockReturnValueOnce(8)
        .mockReturnValueOnce(14)
        .mockReturnValueOnce(10)
        .mockReturnValueOnce(16);

      expect(service.rollAbilityScores()).toEqual([18, 16, 14, 12, 10, 8]);
    });
  });

  describe('modeLabel', () => {
    it('returns empty string for normal mode', () => {
      expect(service.modeLabel('normal')).toBe('');
    });

    it('returns formatted label for advantage/disadvantage', () => {
      expect(service.modeLabel('advantage')).toBe(' (ADVANTAGE)');
      expect(service.modeLabel('disadvantage')).toBe(' (DISADVANTAGE)');
    });
  });

  describe('signed', () => {
    it('adds plus to positive numbers and zero', () => {
      expect(service.signed(3)).toBe('+3');
      expect(service.signed(0)).toBe('+0');
    });

    it('keeps minus for negative numbers', () => {
      expect(service.signed(-2)).toBe('-2');
    });
  });
});
