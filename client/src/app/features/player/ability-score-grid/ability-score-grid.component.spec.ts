import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AbilityScoreGridComponent } from './ability-score-grid.component';

describe('AbilityScoreGridComponent', () => {
  let fixture: ComponentFixture<AbilityScoreGridComponent>;
  let el: HTMLElement;

  beforeEach(() => {
    fixture = TestBed.createComponent(AbilityScoreGridComponent);
    const component = fixture.componentInstance;
    // Rogue 11: proficient in DEX and INT saves, proficiency +4
    component.char = {
      char_name: 'Edrann',
      char_level: 11,
      proficiency_bonus: 4,
      saving_throws: ['DEX', 'INT'],
      stats: { STR: 12, DEX: 20, CON: 16, INT: 16, WIS: 14, CHA: 16 },
    } as any;
    component.entries = [
      { key: 'STR', value: 12 },
      { key: 'DEX', value: 20 },
    ];
    component.getModifierString = (score: number) => {
      const mod = Math.floor((score - 10) / 2);
      return mod >= 0 ? `+${mod}` : `${mod}`;
    };
    fixture.detectChanges();
    el = fixture.nativeElement;
  });

  const cards = () => Array.from(el.querySelectorAll('article'));

  it('leads with the modifier and shows the score underneath', () => {
    const dex = cards()[1];
    expect(dex.textContent).toContain('+5');
    expect(dex.querySelector('[aria-label="DEX score 20"]')).not.toBeNull();
  });

  it('shows the save bonus that is rolled, marking proficient saves', () => {
    const [str, dex] = cards().map((c) => c.querySelectorAll('button')[1] as HTMLButtonElement);
    expect(str.textContent).toContain('+1');
    expect(str.getAttribute('aria-label')).not.toContain('proficient');

    expect(dex.textContent).toContain('+9'); // +5 DEX + 4 proficiency
    expect(dex.getAttribute('aria-label')).toContain('(proficient)');
    expect(dex.className).toContain('text-accent');
  });

  it('emits the ability for check and save', () => {
    const component = fixture.componentInstance;
    const checks: string[] = [];
    const saves: string[] = [];
    component.abilityCheck.subscribe((k) => checks.push(k));
    component.savingThrow.subscribe((k) => saves.push(k));

    const [check, save] = Array.from(cards()[1].querySelectorAll('button')) as HTMLButtonElement[];
    check.click();
    save.click();
    expect(checks).toEqual(['DEX']);
    expect(saves).toEqual(['DEX']);
  });
});
