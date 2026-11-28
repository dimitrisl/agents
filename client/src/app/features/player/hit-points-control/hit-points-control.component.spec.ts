import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HitPointsControlComponent } from './hit-points-control.component';

describe('HitPointsControlComponent', () => {
  let component: HitPointsControlComponent;
  let fixture: ComponentFixture<HitPointsControlComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HitPointsControlComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(HitPointsControlComponent);
    component = fixture.componentInstance;
    component.current = 20;
    component.max = 30;
    component.temp = 5;
    fixture.detectChanges();
  });

  it('should create and calculate percentage correctly', () => {
    expect(component).toBeTruthy();
    expect(component.percentage).toBeCloseTo(66.67, 1);
  });

  it('should open and manipulate quick pad numpad value', () => {
    component.openQuickPad();
    expect(component.showQuickPad()).toBe(true);
    expect(component.numpadValue()).toBe('0');

    component.appendDigit('1');
    component.appendDigit('5');
    expect(component.numpadValue()).toBe('15');

    component.addPill(10);
    expect(component.numpadValue()).toBe('25');

    component.backspace();
    expect(component.numpadValue()).toBe('2');

    component.clearNumpad();
    expect(component.numpadValue()).toBe('0');
  });

  it('should emit applyDamage, applyHeal, and setTempHp from quick pad', () => {
    const damageSpy = jest.spyOn(component.applyDamage, 'emit');
    const healSpy = jest.spyOn(component.applyHeal, 'emit');
    const tempSpy = jest.spyOn(component.setTempHp, 'emit');

    component.openQuickPad();
    component.appendDigit('8');
    component.executeDamage();
    expect(damageSpy).toHaveBeenCalledWith(8);
    expect(component.showQuickPad()).toBe(false);

    component.openQuickPad();
    component.appendDigit('1');
    component.appendDigit('2');
    component.executeHeal();
    expect(healSpy).toHaveBeenCalledWith(12);

    component.openQuickPad();
    component.appendDigit('5');
    component.executeSetTemp();
    expect(tempSpy).toHaveBeenCalledWith(5);
  });

  it('should toggle death saves and emit rollDeathSave', () => {
    const deathSaveSpy = jest.spyOn(component.deathSaveChange, 'emit');
    const rollSpy = jest.spyOn(component.rollDeathSave, 'emit');

    component.deathSaves = { successes: 1, failures: 0 };
    component.toggleDeathSave('successes', 2);
    expect(deathSaveSpy).toHaveBeenCalledWith({ type: 'successes', value: 2 });

    component.triggerRollDeathSave();
    expect(rollSpy).toHaveBeenCalled();
  });

  it('shows Exhaustion 6 deceased notice and blocks heal/temp/death-save inputs when isDeceasedByExhaustion is true', () => {
    fixture.componentRef.setInput('current', 0);
    fixture.componentRef.setInput('max', 30);
    fixture.componentRef.setInput('isDeceasedByExhaustion', true);
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Deceased (Exhaustion 6)');
    const healSpy = jest.spyOn(component.applyHeal, 'emit');
    const tempSpy = jest.spyOn(component.setTempHp, 'emit');
    const rollSpy = jest.spyOn(component.rollDeathSave, 'emit');

    component.appendDigit('9');
    component.executeHeal();
    component.executeSetTemp();
    component.triggerRollDeathSave();

    expect(healSpy).not.toHaveBeenCalled();
    expect(tempSpy).not.toHaveBeenCalled();
    expect(rollSpy).not.toHaveBeenCalled();
  });

  it('supports Raw / ½ Resist / ×2 Vuln / 0 Immune mitigation and matched defense pills', () => {
    fixture.componentRef.setInput('damageResistances', ['Fire']);
    fixture.componentRef.setInput('damageImmunities', ['Poison']);
    fixture.componentRef.setInput('damageVulnerabilities', ['Cold']);
    fixture.detectChanges();

    const damageSpy = jest.spyOn(component.applyDamage, 'emit');
    const immuneSpy = jest.spyOn(component.damageImmuneApplied, 'emit');

    // Resistance halves damage rounding down (25 -> 12)
    component.openQuickPad(25);
    fixture.detectChanges();
    (document.querySelector('[data-testid="hp-defense-pill-Fire"]') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(component.adjustedDamageAmount).toBe(12);
    component.executeDamage();
    expect(damageSpy).toHaveBeenCalledWith(12);

    // Vulnerability doubles damage (15 -> 30)
    component.openQuickPad(15);
    fixture.detectChanges();
    (document.querySelector('[data-testid="hp-defense-pill-Cold"]') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(component.adjustedDamageAmount).toBe(30);
    component.executeDamage();
    expect(damageSpy).toHaveBeenCalledWith(30);

    // Immunity emits damageImmuneApplied without applying HP loss
    damageSpy.mockClear();
    component.openQuickPad(18);
    fixture.detectChanges();
    (document.querySelector('[data-testid="hp-defense-pill-Poison"]') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(component.adjustedDamageAmount).toBe(0);
    component.executeDamage();
    expect(damageSpy).not.toHaveBeenCalled();
    expect(immuneSpy).toHaveBeenCalledWith({ raw: 18, label: 'Poison', mode: 'immune' });

    // Resisted 1 damage rounding down to 0 emits resist mode without firing immune copy
    immuneSpy.mockClear();
    component.openQuickPad(1);
    fixture.detectChanges();
    (document.querySelector('[data-testid="hp-defense-pill-Fire"]') as HTMLButtonElement).click();
    fixture.detectChanges();
    component.executeDamage();
    expect(immuneSpy).toHaveBeenCalledWith({ raw: 1, label: 'Fire', mode: 'resist' });

    // Same-type Resist + Vulnerability pills stay distinct, and Petrified exposes Petrified (All)
    fixture.componentRef.setInput('damageResistances', ['Acid']);
    fixture.componentRef.setInput('damageVulnerabilities', ['Acid']);
    fixture.componentRef.setInput('activeConditions', ['Petrified']);
    fixture.detectChanges();
    component.openQuickPad(20);
    fixture.detectChanges();
    const acidPills = Array.from(document.querySelectorAll('[data-testid="hp-defense-pill-Acid"]')) as HTMLButtonElement[];
    expect(acidPills.length).toBe(2);
    acidPills[0].click(); // vuln Acid
    fixture.detectChanges();
    expect(component.mitigationMode()).toBe('vuln');
    acidPills[1].click(); // resist Acid (switches instead of toggling off!)
    fixture.detectChanges();
    expect(component.mitigationMode()).toBe('resist');
    const petrifiedPill = document.querySelector('[data-testid="hp-defense-pill-Petrified (All)"]') as HTMLButtonElement;
    expect(petrifiedPill).toBeTruthy();
  });
});
