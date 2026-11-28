import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ConditionsModalComponent } from './conditions-modal.component';

describe('ConditionsModalComponent', () => {
  let fixture: ComponentFixture<ConditionsModalComponent>;
  let component: ConditionsModalComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ConditionsModalComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(ConditionsModalComponent);
    component = fixture.componentInstance;
    component.open = true;
    component.char = {
      char_name: 'Kaelen',
      char_class: 'Paladin',
      char_level: 10,
      race: 'Elf',
      dnd_edition: '2024 Revision (5.5e)',
      conditions: [],
    };
    component.initialConditions = [];
    fixture.detectChanges();
  });

  it('surfaces non-blocking antidote warnings and active effect summaries without disabling toggles', () => {
    expect(document.body.textContent).toContain('antidotes detected');

    const frightenedBtn = document.querySelector(
      '[data-testid="condition-toggle-Frightened"]'
    ) as HTMLButtonElement;
    expect(frightenedBtn.disabled).toBe(false);
    frightenedBtn.click();
    fixture.detectChanges();

    const warnings = document.querySelector('[data-testid="conditions-antidote-warnings"]');
    expect(warnings?.textContent).toContain('Aura of Courage');

    const effects = document.querySelector('[data-testid="conditions-effects-summary"]');
    expect(effects?.textContent).toContain('Frightened');

    const invisibleBtn = document.querySelector(
      '[data-testid="condition-toggle-Invisible"]'
    ) as HTMLButtonElement;
    invisibleBtn.click();
    fixture.detectChanges();
    expect(effects?.textContent).toContain('ADV Init (2024)');

    const saved: Array<{ conditions: string[]; concentratingOn: string }> = [];
    component.save.subscribe((v) => saved.push(v));
    component.saveAndClose();
    expect(saved[0].conditions).toEqual(['Frightened', 'Invisible']);
  });

  it('discards uncommitted toggles when reopened after cancel', () => {
    const proneBtn = document.querySelector('[data-testid="condition-toggle-Prone"]') as HTMLButtonElement;
    proneBtn.click();
    fixture.detectChanges();
    expect(component.selectedConditions.has('Prone')).toBe(true);

    // Close & reopen without saving
    fixture.componentRef.setInput('open', false);
    fixture.detectChanges();
    fixture.componentRef.setInput('open', true);
    fixture.detectChanges();
    expect(component.selectedConditions.has('Prone')).toBe(false);
  });

  it('preserves unsaved toggles while open if background WS updates initialConditions', () => {
    const poisonedBtn = document.querySelector('[data-testid="condition-toggle-Poisoned"]') as HTMLButtonElement;
    poisonedBtn.click();
    fixture.detectChanges();
    expect(component.selectedConditions.has('Poisoned')).toBe(true);

    fixture.componentRef.setInput('initialConditions', ['Grappled']);
    fixture.detectChanges();
    expect(component.selectedConditions.has('Poisoned')).toBe(true);
    expect(component.selectedConditions.has('Grappled')).toBe(false);
  });
});
