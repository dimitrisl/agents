import { InitiativePanelComponent } from './initiative-panel.component';
import { InitiativeCombatant } from '../../../../core/models/initiative.model';
import { BestiaryMonster } from '../../../../core/models/bestiary.model';

describe('InitiativePanelComponent', () => {
  let component: InitiativePanelComponent;
  let mockCombatant: InitiativeCombatant;

  const mockMonster: BestiaryMonster = {
    id: 'srd_goblin_2014',
    name: 'Goblin',
    edition: '2014',
    origin: 'official',
    is_public: true,
    size: 'Small',
    type: 'humanoid',
    alignment: 'neutral evil',
    cr: '1/4',
    cr_numeric: 0.25,
    ac: 15,
    hp: 7,
    max_hp: 7,
    speed: '30 ft.',
    stats: { str: 8, dex: 14, con: 10, int: 10, wis: 8, cha: 8 },
    traits: [],
    actions: [],
  };

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

  describe('Quick-Add Monster search and filtering', () => {
    it('initializes with Official and Mine ON and Community OFF', () => {
      expect(component.includeOfficial).toBe(true);
      expect(component.includeMine).toBe(true);
      expect(component.includeCommunity).toBe(false);
      expect(component.isDropdownOpen).toBe(false);
    });

    it('toggles source chips properly', () => {
      component.toggleSource('official');
      expect(component.includeOfficial).toBe(false);

      component.toggleSource('mine');
      expect(component.includeMine).toBe(false);

      component.toggleSource('community');
      expect(component.includeCommunity).toBe(true);
    });

    it('emits addMonster on selectMonster and closes dropdown', () => {
      let emittedMonster: BestiaryMonster | undefined;
      component.addMonster.subscribe((m) => (emittedMonster = m));

      component.isDropdownOpen = true;
      component.quickAddQuery = 'Goblin';
      component.quickAddResults = [mockMonster];

      component.selectMonster(mockMonster);

      expect(emittedMonster).toEqual(mockMonster);
      expect(component.isDropdownOpen).toBe(false);
      expect(component.quickAddQuery).toBe('');
      expect(component.quickAddResults).toEqual([]);
    });

    it('closes dropdown on onEscape', () => {
      component.isDropdownOpen = true;
      component.onEscape();
      expect(component.isDropdownOpen).toBe(false);
    });
  });
});
