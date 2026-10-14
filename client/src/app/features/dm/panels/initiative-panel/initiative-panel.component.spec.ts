import { InitiativePanelComponent } from './initiative-panel.component';
import { InitiativeCombatant } from '../../../../core/models/initiative.model';

describe('InitiativePanelComponent', () => {
  let component: InitiativePanelComponent;
  let mockCombatant: InitiativeCombatant;

  beforeEach(() => {
    component = new InitiativePanelComponent();
    mockCombatant = {
      id: 'c1',
      name: 'Orc Warrior',
      initiative: 12,
      hp: 20,
      max_hp: 30,
      ac: 13,
      dex: 10,
      is_player: false,
      conditions: [],
    };
  });

  describe('onHpInput delta & absolute calculations', () => {
    it('sets absolute HP value directly when a positive number is typed', () => {
      let emitted: { combatant: InitiativeCombatant; hp: number } | undefined;
      component.hpChange.subscribe(e => emitted = e);

      const input = { value: '15' } as HTMLInputElement;
      component.onHpInput(mockCombatant, input);

      expect(input.value).toBe('15');
      expect(emitted?.hp).toBe(15);
    });

    it('subtracts damage when delta with minus sign is typed (e.g. -7)', () => {
      let emitted: { combatant: InitiativeCombatant; hp: number } | undefined;
      component.hpChange.subscribe(e => emitted = e);

      const input = { value: '-7' } as HTMLInputElement;
      component.onHpInput(mockCombatant, input);

      expect(input.value).toBe('13'); // 20 - 7 = 13
      expect(emitted?.hp).toBe(13);
    });

    it('adds healing when delta with plus sign is typed (e.g. +6)', () => {
      let emitted: { combatant: InitiativeCombatant; hp: number } | undefined;
      component.hpChange.subscribe(e => emitted = e);

      const input = { value: '+6' } as HTMLInputElement;
      component.onHpInput(mockCombatant, input);

      expect(input.value).toBe('26'); // 20 + 6 = 26
      expect(emitted?.hp).toBe(26);
    });

    it('clamps HP to max_hp on overheal', () => {
      let emitted: { combatant: InitiativeCombatant; hp: number } | undefined;
      component.hpChange.subscribe(e => emitted = e);

      const input = { value: '+50' } as HTMLInputElement;
      component.onHpInput(mockCombatant, input);

      expect(input.value).toBe('30'); // capped at max_hp (30)
      expect(emitted?.hp).toBe(30);
    });

    it('clamps HP to 0 when overkill damage is taken', () => {
      let emitted: { combatant: InitiativeCombatant; hp: number } | undefined;
      component.hpChange.subscribe(e => emitted = e);

      const input = { value: '-50' } as HTMLInputElement;
      component.onHpInput(mockCombatant, input);

      expect(input.value).toBe('0');
      expect(emitted?.hp).toBe(0);
    });

    it('restores current HP if invalid text is typed', () => {
      let emitted: { combatant: InitiativeCombatant; hp: number } | undefined;
      component.hpChange.subscribe(e => emitted = e);

      const input = { value: 'not-a-number' } as HTMLInputElement;
      component.onHpInput(mockCombatant, input);

      expect(input.value).toBe('20');
      expect(emitted?.hp).toBe(20);
    });
  });
});
