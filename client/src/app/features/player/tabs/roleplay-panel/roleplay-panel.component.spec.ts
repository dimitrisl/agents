import { ComponentFixture, TestBed } from '@angular/core/testing';
import { RoleplayPanelComponent } from './roleplay-panel.component';
import { CharacterSchema } from '../../../../core/models/character.model';

describe('RoleplayPanelComponent', () => {
  let fixture: ComponentFixture<RoleplayPanelComponent>;
  let component: RoleplayPanelComponent;

  const mockChar: CharacterSchema = {
    char_id: 'rp-1',
    char_name: 'Valen Stormblade',
    char_class: 'Paladin',
    char_level: 7,
    race: 'High Elf',
    background: 'Noble',
    alignment: 'Lawful Good',
    armor_class: 19,
    hp_max: 64,
    speed: 30,
    proficiency_bonus: 3,
    stats: { STR: 18, DEX: 14, CON: 14, INT: 10, WIS: 12, CHA: 16 },
    personality_traits: 'Always calm under pressure.',
    ideals: 'Protect the weak.',
    bonds: 'Oath to the Silver Order.',
    flaws: 'Stubborn pride.',
    backstory: 'Forged in the fires of Barovia.',
    languages: ['Common', 'Elvish'],
    tool_proficiencies: ['Dragonchess Set'],
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RoleplayPanelComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(RoleplayPanelComponent);
    component = fixture.componentInstance;
    component.char = JSON.parse(JSON.stringify(mockChar));
    fixture.detectChanges();
  });

  it('renders desktop layout with Languages & Tools by default', () => {
    const text = (fixture.nativeElement as HTMLElement).textContent || '';
    expect(text).toContain('Languages & Tools');
    expect(text).toContain('Always calm under pressure.');
  });

  it('renders compact mobile lore view without duplicate Languages & Tools when compactMobile is true', () => {
    fixture.componentRef.setInput('compactMobile', true);
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="mobile-lore-view"]')).toBeTruthy();
    expect(el.textContent).toContain('Lawful Good');
    expect(el.textContent).toContain('Always calm under pressure.');
    expect(el.textContent).toContain('Forged in the fires of Barovia.');
    expect(el.textContent).not.toContain('Languages & Tools');
  });
});
