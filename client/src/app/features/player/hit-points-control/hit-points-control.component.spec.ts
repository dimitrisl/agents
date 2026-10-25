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
});
