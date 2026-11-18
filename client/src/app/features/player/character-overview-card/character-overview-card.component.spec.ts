import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CharacterOverviewCardComponent } from './character-overview-card.component';
import { CharacterSchema } from '../../../core/models/character.model';

describe('CharacterOverviewCardComponent', () => {
  let fixture: ComponentFixture<CharacterOverviewCardComponent>;
  let component: CharacterOverviewCardComponent;

  const baseChar: CharacterSchema = {
    char_id: 'mc-1',
    char_name: 'Lyra',
    char_class: 'Paladin',
    subclass: 'Oath of Devotion',
    char_level: 8,
    classes: [
      { class_name: 'Paladin', level: 5, subclass: 'Oath of Devotion' },
      { class_name: 'Sorcerer', level: 3, subclass: 'Draconic Sorcery' },
    ],
    hit_dice: '5d10, 3d6',
    race: 'Human',
    background: 'Noble',
    armor_class: 18,
    hp_max: 68,
    hp_current: 68,
    speed: 20,
    heavy_armor_speed_penalty: 10,
    proficiency_bonus: 3,
    stats: { STR: 12, DEX: 12, CON: 14, INT: 10, WIS: 12, CHA: 16 },
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CharacterOverviewCardComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(CharacterOverviewCardComponent);
    component = fixture.componentInstance;
    component.char = { ...baseChar };
    component.abilityEntries = [
      { key: 'STR', value: 12 },
      { key: 'DEX', value: 12 },
      { key: 'CON', value: 14 },
      { key: 'INT', value: 10 },
      { key: 'WIS', value: 12 },
      { key: 'CHA', value: 16 },
    ];
    component.getModifierString = (val: number) => {
      const m = Math.floor((val - 10) / 2);
      return m >= 0 ? `+${m}` : `${m}`;
    };
    fixture.detectChanges();
  });

  it('displays full multiclass identity, subclasses, hit dice pools, and heavy armor STR penalty', () => {
    const text = (fixture.nativeElement as HTMLElement).textContent || '';
    expect(text).toContain('Paladin 5 / Sorcerer 3');
    expect(text).toContain('(Oath of Devotion / Draconic Sorcery)');
    expect(text).toContain('5d10, 3d6');
    expect(text).toContain('-10ft STR');
  });
});
