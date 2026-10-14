import { PartyPanelComponent } from './party-panel.component';
import { PartyMember } from '../../../../core/models/party.model';

describe('PartyPanelComponent', () => {
  let component: PartyPanelComponent;
  let mockMember: PartyMember;

  beforeEach(() => {
    component = new PartyPanelComponent();
    mockMember = {
      char_id: 'm1',
      name: 'Thorin',
      char_class: 'Paladin',
      level: 5,
      hp_current: 35,
      hp_max: 45,
      ac: 18,
      passive_perception: 12,
      conditions: [],
    };
  });

  describe('onHpInput delta & absolute calculations', () => {
    it('sets absolute HP value directly when a positive number is typed', () => {
      let emitted: { member: PartyMember; hp: number } | undefined;
      component.setHp.subscribe(e => emitted = e);

      const input = { value: '40' } as HTMLInputElement;
      component.onHpInput(mockMember, input);

      expect(input.value).toBe('40');
      expect(emitted?.hp).toBe(40);
    });

    it('subtracts damage when delta with minus sign is typed (e.g. -12)', () => {
      let emitted: { member: PartyMember; hp: number } | undefined;
      component.setHp.subscribe(e => emitted = e);

      const input = { value: '-12' } as HTMLInputElement;
      component.onHpInput(mockMember, input);

      expect(input.value).toBe('23'); // 35 - 12 = 23
      expect(emitted?.hp).toBe(23);
    });

    it('adds healing when delta with plus sign is typed (e.g. +8)', () => {
      let emitted: { member: PartyMember; hp: number } | undefined;
      component.setHp.subscribe(e => emitted = e);

      const input = { value: '+8' } as HTMLInputElement;
      component.onHpInput(mockMember, input);

      expect(input.value).toBe('43'); // 35 + 8 = 43
      expect(emitted?.hp).toBe(43);
    });

    it('clamps HP to max_hp on overheal', () => {
      let emitted: { member: PartyMember; hp: number } | undefined;
      component.setHp.subscribe(e => emitted = e);

      const input = { value: '+20' } as HTMLInputElement;
      component.onHpInput(mockMember, input);

      expect(input.value).toBe('45'); // clamped to max_hp (45)
      expect(emitted?.hp).toBe(45);
    });

    it('clamps HP to 0 when overkill damage is taken', () => {
      let emitted: { member: PartyMember; hp: number } | undefined;
      component.setHp.subscribe(e => emitted = e);

      const input = { value: '-100' } as HTMLInputElement;
      component.onHpInput(mockMember, input);

      expect(input.value).toBe('0');
      expect(emitted?.hp).toBe(0);
    });

    it('restores current HP if invalid text is typed', () => {
      let emitted: { member: PartyMember; hp: number } | undefined;
      component.setHp.subscribe(e => emitted = e);

      const input = { value: 'invalid' } as HTMLInputElement;
      component.onHpInput(mockMember, input);

      expect(input.value).toBe('35');
      expect(emitted?.hp).toBe(35);
    });
  });
});
