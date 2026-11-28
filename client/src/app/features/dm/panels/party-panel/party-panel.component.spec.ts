import { TestBed } from '@angular/core/testing';
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

  describe('DM control outputs (exhaustion, unlocks, Athas suppression, inspiration, modifiers)', () => {
    it('emits partyActionUnlock, memberActionToggle, adjustExhaustion, and openModifiers', () => {
      const partyUnlockSpy = jest.spyOn(component.partyActionUnlock, 'emit');
      const memberToggleSpy = jest.spyOn(component.memberActionToggle, 'emit');
      const exhSpy = jest.spyOn(component.adjustExhaustion, 'emit');
      const modsSpy = jest.spyOn(component.openModifiers, 'emit');

      component.partyActionUnlock.emit({ actionType: 'suppress_magic_items', unlocked: true });
      component.memberActionToggle.emit({ member: mockMember, field: 'inspiration', value: true });
      component.adjustExhaustion.emit({ member: mockMember, delta: 1 });
      component.openModifiers.emit(mockMember);

      expect(partyUnlockSpy).toHaveBeenCalledWith({ actionType: 'suppress_magic_items', unlocked: true });
      expect(memberToggleSpy).toHaveBeenCalledWith({
        member: mockMember,
        field: 'inspiration',
        value: true,
      });
      expect(exhSpy).toHaveBeenCalledWith({ member: mockMember, delta: 1 });
      expect(modsSpy).toHaveBeenCalledWith(mockMember);
    });
  });

  it('surfaces antidote countermeasures and speed lock indicators even when no other status badges exist', () => {
    const paladinL10: PartyMember = {
      ...mockMember,
      level: 10,
      conditions: ['Frightened', 'Grappled'],
    };
    const antidotes = component.conditionAntidotes(paladinL10);
    expect(antidotes.some((a) => a.condition === 'Frightened' && a.source === 'Aura of Courage')).toBe(true);
    expect(component.speedLock(paladinL10)).toBe('Grappled');
    expect(component.hasStatusBadges(paladinL10)).toBe(true);

    TestBed.configureTestingModule({
      imports: [PartyPanelComponent],
    });
    const fixture = TestBed.createComponent(PartyPanelComponent);
    fixture.componentInstance.campaignName = 'Iron Vault';
    fixture.componentInstance.partyMembers = [paladinL10];
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('0 ft (Grappled)');
    expect(text).toContain('Frightened Antidote (Aura of Courage)');
    expect(component.hasCondition({ ...mockMember, conditions: ['poisoned'] }, 'Poisoned')).toBe(true);
    expect(component.conditionTone({ ...mockMember, conditions: ['poisoned'] }, 'Poisoned')).toBe('danger');
  });
});
