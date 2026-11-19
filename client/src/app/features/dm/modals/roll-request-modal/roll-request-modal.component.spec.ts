import { ComponentFixture, TestBed } from '@angular/core/testing';
import { RollRequestModalComponent } from './roll-request-modal.component';

describe('RollRequestModalComponent', () => {
  let fixture: ComponentFixture<RollRequestModalComponent>;
  let component: RollRequestModalComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RollRequestModalComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(RollRequestModalComponent);
    component = fixture.componentInstance;
    component.open = true;
    component.partyMembers = [
      {
        char_id: 'c1',
        name: 'Elena',
        char_class: 'Fighter',
        level: 3,
        hp_current: 28,
        hp_max: 28,
        ac: 18,
        conditions: [],
      },
      {
        char_id: 'c2',
        name: 'Lyra',
        char_class: 'Sorcerer',
        level: 3,
        hp_current: 20,
        hp_max: 20,
        ac: 14,
        conditions: [],
      },
    ];
  });

  function renderSelectLabels(): string[] {
    fixture.detectChanges();
    const labels = Array.from(document.querySelectorAll('.cdk-overlay-container label'));
    return labels.map((el) => (el.textContent || '').trim());
  }

  afterEach(() => {
    component.open = false;
    fixture.detectChanges();
    fixture.destroy();
  });

  it('shows Stat selector for saving_throw and Skill selector for skill_check', () => {
    fixture.componentRef.setInput('rollType', 'saving_throw');
    let labelTexts = renderSelectLabels();
    expect(labelTexts.some((t) => t.startsWith('Stat:'))).toBe(true);

    fixture.componentRef.setInput('rollType', 'skill_check');
    labelTexts = renderSelectLabels();
    expect(labelTexts.some((t) => t.startsWith('Skill:'))).toBe(true);
    expect(labelTexts.some((t) => t.startsWith('Stat:'))).toBe(false);
  });

  it('hides the Stat/Skill selector when rollType is initiative and updates placeholder', () => {
    fixture.componentRef.setInput('rollType', 'initiative');
    const labelTexts = renderSelectLabels();

    expect(labelTexts.some((t) => t.startsWith('Roll Type:'))).toBe(true);
    expect(labelTexts.some((t) => t.startsWith('Stat:'))).toBe(false);
    expect(labelTexts.some((t) => t.startsWith('Skill:'))).toBe(false);

    const reasonInput = document.querySelector('.cdk-overlay-container input[type="text"]') as HTMLInputElement;
    expect(reasonInput?.placeholder).toContain('Initiative');
  });

  it('renders All Party Members option when multiple heroes exist and emits requestRoll', () => {
    component.rollType = 'initiative';
    fixture.detectChanges();
    const spy = jest.spyOn(component.requestRoll, 'emit');

    const overlay = document.querySelector('.cdk-overlay-container')!;
    const options = Array.from(overlay.querySelectorAll('option')).map((o) => o.getAttribute('value'));
    expect(options).toContain('ALL');

    const buttons = Array.from(overlay.querySelectorAll('button'));
    const submitBtn = buttons.find((b) => (b.textContent || '').includes('Request Roll'))!;
    expect(submitBtn).toBeTruthy();
    submitBtn.click();

    expect(spy).toHaveBeenCalledTimes(1);
  });
});
