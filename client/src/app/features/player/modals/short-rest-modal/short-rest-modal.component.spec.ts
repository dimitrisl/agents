import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ShortRestModalComponent } from './short-rest-modal.component';

describe('ShortRestModalComponent', () => {
  let component: ShortRestModalComponent;
  let fixture: ComponentFixture<ShortRestModalComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ShortRestModalComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(ShortRestModalComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => {
    fixture.componentRef.setInput('open', false);
    fixture.detectChanges();
    document.querySelectorAll('.cdk-overlay-container').forEach((el) => el.remove());
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('does not render hit die pool selector when hitDieOptions has 1 or 0 options', () => {
    fixture.componentRef.setInput('availableHitDice', 3);
    fixture.componentRef.setInput('hitDieOptions', [{ className: 'Fighter', level: 3, dieSize: 10 }]);
    fixture.componentRef.setInput('open', true);
    fixture.detectChanges();

    const selectEl = document.querySelector('#short-rest-die-pool');
    expect(selectEl).toBeNull();
  });

  it('renders hit die pool selector when character is multiclassed with multiple options', () => {
    fixture.componentRef.setInput('availableHitDice', 5);
    fixture.componentRef.setInput('hitDieOptions', [
      { className: 'Barbarian', level: 3, dieSize: 12 },
      { className: 'Wizard', level: 2, dieSize: 6 },
    ]);
    fixture.componentRef.setInput('selectedDieSize', 12);
    fixture.componentRef.setInput('open', true);
    fixture.detectChanges();

    const selectEl = document.querySelector<HTMLSelectElement>('#short-rest-die-pool');
    expect(selectEl).not.toBeNull();

    const options = selectEl!.querySelectorAll('option');
    expect(options.length).toBe(2);
    expect(options[0].textContent).toContain('d12');
    expect(options[0].textContent).toContain('Barbarian');
    expect(options[1].textContent).toContain('d6');
    expect(options[1].textContent).toContain('Wizard');
  });

  it('emits selectedDieSizeChange when the die pool selection changes', () => {
    jest.spyOn(component.selectedDieSizeChange, 'emit');
    fixture.componentRef.setInput('availableHitDice', 5);
    fixture.componentRef.setInput('hitDieOptions', [
      { className: 'Barbarian', level: 3, dieSize: 12 },
      { className: 'Wizard', level: 2, dieSize: 6 },
    ]);
    fixture.componentRef.setInput('selectedDieSize', 12);
    fixture.componentRef.setInput('open', true);
    fixture.detectChanges();

    const selectEl = document.querySelector<HTMLSelectElement>('#short-rest-die-pool');
    expect(selectEl).not.toBeNull();

    selectEl!.selectedIndex = 1;
    selectEl!.dispatchEvent(new Event('change'));
    fixture.detectChanges();

    expect(component.selectedDieSizeChange.emit).toHaveBeenCalledWith(6);
  });

  it('emits executeShortRest when clicking spend hit dice button', () => {
    jest.spyOn(component.executeShortRest, 'emit');
    fixture.componentRef.setInput('availableHitDice', 2);
    fixture.componentRef.setInput('open', true);
    fixture.detectChanges();

    const buttons = Array.from(document.querySelectorAll<HTMLButtonElement>('button'));
    const spendBtn = buttons.find((b) => b.textContent?.includes('Spend Hit Dice'));
    expect(spendBtn).toBeDefined();
    spendBtn!.click();

    expect(component.executeShortRest.emit).toHaveBeenCalled();
  });

  it('displays warning and hides spend button when availableHitDice is 0', () => {
    fixture.componentRef.setInput('availableHitDice', 0);
    fixture.componentRef.setInput('open', true);
    fixture.detectChanges();

    const buttons = Array.from(document.querySelectorAll<HTMLButtonElement>('button'));
    const spendBtn = buttons.find((b) => b.textContent?.includes('Spend Hit Dice'));
    expect(spendBtn).toBeUndefined();

    const warningEl = document.querySelector('.text-red');
    expect(warningEl).not.toBeNull();
    expect(warningEl!.textContent).toContain('no available Hit Dice remaining');
  });

  it('allows Warlock with hasPactSlots to take a short rest even when availableHitDice is 0', () => {
    jest.spyOn(component.executeShortRest, 'emit');
    fixture.componentRef.setInput('availableHitDice', 0);
    fixture.componentRef.setInput('hasPactSlots', true);
    fixture.componentRef.setInput('open', true);
    fixture.detectChanges();

    const buttons = Array.from(document.querySelectorAll<HTMLButtonElement>('button'));
    const pactBtn = buttons.find((b) => b.textContent?.includes('Recover Pact Slots'));
    expect(pactBtn).toBeDefined();
    pactBtn!.click();

    expect(component.executeShortRest.emit).toHaveBeenCalled();
  });

  it('caps selectedClassMaxDice to the selected multiclass hit die pool level', () => {
    fixture.componentRef.setInput('availableHitDice', 6);
    fixture.componentRef.setInput('hitDieOptions', [
      { className: 'Barbarian', level: 5, dieSize: 12 },
      { className: 'Wizard', level: 2, dieSize: 6 },
    ]);
    fixture.componentRef.setInput('selectedDieSize', 6);
    fixture.componentRef.setInput('diceToSpend', 5);
    fixture.componentRef.setInput('open', true);
    fixture.detectChanges();

    expect(component.selectedClassMaxDice).toBe(2);
  });
});
