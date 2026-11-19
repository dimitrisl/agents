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

  it('shows check modifier with 2024 exhaustion/DM bonus and renders DIS badges for 2014 exhaustion with bypass support', () => {
    const component = fixture.componentInstance;
    fixture.componentRef.setInput('char', {
      ...component.char,
      dnd_edition: '2024 Revision (5.5e)',
      exhaustion_level: 2,
      dm_modifiers: { ability_checks_bonus: 2, saving_throws_bonus: 1 },
    } as any);
    fixture.detectChanges();

    // DEX mod +5 - 4 (Exh) + 2 (DM Check) = +3 on Check button
    const [dexCheck, dexSave] = Array.from(cards()[1].querySelectorAll('button')) as HTMLButtonElement[];
    expect(dexCheck.textContent).toContain('+3');
    expect(dexSave.textContent).toContain('+6'); // +5 + 4 - 4 + 1
    expect(dexCheck.textContent).not.toContain('DIS');

    // Switch to 2014 Edition Level 1 -> DIS on Check ONLY
    fixture.componentRef.setInput('char', {
      ...component.char,
      dnd_edition: '2014 Edition',
      exhaustion_level: 1,
      exhaustion_bypass: false,
    } as any);
    fixture.detectChanges();
    const [l1Check, l1Save] = Array.from(cards()[1].querySelectorAll('button')) as HTMLButtonElement[];
    expect(l1Check.textContent).toContain('DIS');
    expect(l1Save.textContent).not.toContain('DIS');

    // Level 3 in 2014 -> DIS on BOTH Check & Save; bypass clears DIS
    fixture.componentRef.setInput('char', {
      ...component.char,
      dnd_edition: '2014 Edition',
      exhaustion_level: 3,
      exhaustion_bypass: false,
    } as any);
    fixture.detectChanges();
    const [l3Check, l3Save] = Array.from(cards()[1].querySelectorAll('button')) as HTMLButtonElement[];
    expect(l3Check.textContent).toContain('DIS');
    expect(l3Save.textContent).toContain('DIS');

    fixture.componentRef.setInput('char', {
      ...component.char,
      dnd_edition: '2014 Edition',
      exhaustion_level: 3,
      exhaustion_bypass: true,
    } as any);
    fixture.detectChanges();
    const [bypassCheck, bypassSave] = Array.from(cards()[1].querySelectorAll('button')) as HTMLButtonElement[];
    expect(bypassCheck.textContent).not.toContain('DIS');
    expect(bypassSave.textContent).not.toContain('DIS');
  });
});
