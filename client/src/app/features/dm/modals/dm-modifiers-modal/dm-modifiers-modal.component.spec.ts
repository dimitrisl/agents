import { SimpleChange } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { DmModifiersModalComponent, DmModifiersSaveEvent } from './dm-modifiers-modal.component';
import type { PartyMember } from '../../../../core/models/party.model';

describe('DmModifiersModalComponent', () => {
  let fixture: ComponentFixture<DmModifiersModalComponent>;
  let component: DmModifiersModalComponent;

  const sampleMember: PartyMember = {
    char_id: 'pal_1',
    name: 'Theron',
    char_class: 'Paladin',
    level: 5,
    hp_current: 30,
    hp_max: 44,
    ac: 18,
    passive_perception: 12,
    conditions: [],
    exhaustion_level: 2,
    exhaustion_bypass: false,
    magic_items_suppressed: true,
    dm_modifiers: {
      attack_bonus: -2,
      damage_bonus: 3,
      ac_bonus: -1,
      speed_bonus: 5,
      hp_max_bonus: -4,
      initiative_bonus: 2,
      saving_throws_bonus: 1,
      ability_checks_bonus: -1,
      spell_save_dc_bonus: 2,
      passive_perception_bonus: 3,
      note: 'Dark Sun heat',
    },
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DmModifiersModalComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(DmModifiersModalComponent);
    component = fixture.componentInstance;
  });

  it('loads member state on open, clamps exhaustion 0..6, and emits sanitized saveModifiers', () => {
    component.member = sampleMember;
    component.open = true;
    component.ngOnChanges({
      open: new SimpleChange(false, true, true),
      member: new SimpleChange(null, sampleMember, true),
    });
    fixture.detectChanges();

    expect(component.exhaustionLevel).toBe(2);
    expect(component.magicItemsSuppressed).toBe(true);
    expect(component.modifiers.attack_bonus).toBe(-2);
    expect(component.modifiers.note).toBe('Dark Sun heat');

    component.adjustExhaustion(10);
    expect(component.exhaustionLevel).toBe(6);
    component.adjustExhaustion(-1);
    expect(component.exhaustionLevel).toBe(5);

    component.exhaustionBypass = true;
    component.modifiers.ac_bonus = -3;

    let emitted: DmModifiersSaveEvent | undefined;
    component.saveModifiers.subscribe((ev) => (emitted = ev));
    component.submit();

    expect(emitted).toEqual({
      member: sampleMember,
      exhaustion_level: 5,
      exhaustion_bypass: true,
      magic_items_suppressed: true,
      dm_modifiers: expect.objectContaining({
        attack_bonus: -2,
        damage_bonus: 3,
        ac_bonus: -3,
        note: 'Dark Sun heat',
      }),
    });
  });

  it('resets bypass, suppression, and all 10 modifiers on resetModifiers()', () => {
    component.member = sampleMember;
    component.open = true;
    component.ngOnChanges({ open: new SimpleChange(false, true, true) });
    component.exhaustionBypass = true;

    component.resetModifiers();

    expect(component.exhaustionBypass).toBe(false);
    expect(component.magicItemsSuppressed).toBe(false);
    expect(component.modifiers.attack_bonus).toBe(0);
    expect(component.modifiers.note).toBe('');
  });
});
