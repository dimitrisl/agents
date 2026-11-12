import { ComponentFixture, TestBed } from '@angular/core/testing';
import { QuickDiceDrawerComponent } from './quick-dice-drawer.component';
import { DiceService } from '../../../core/services/dice.service';
import { HapticsService } from '../../../core/services/haptics.service';
import { RollToastService } from '../../../core/services/roll-toast.service';

describe('QuickDiceDrawerComponent', () => {
  let component: QuickDiceDrawerComponent;
  let fixture: ComponentFixture<QuickDiceDrawerComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [QuickDiceDrawerComponent],
      providers: [DiceService, HapticsService, RollToastService],
    }).compileComponents();

    fixture = TestBed.createComponent(QuickDiceDrawerComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should add dice to pool and construct formula', () => {
    expect(component.totalDiceCount).toBe(0);
    component.addDie(6);
    component.addDie(6);
    component.addDie(4);
    expect(component.totalDiceCount).toBe(3);
    expect(component.diceFormula).toContain('1d4 + 2d6');

    component.adjustModifier(3);
    expect(component.diceFormula).toContain('+ 3');
  });

  it('should clear dice pool', () => {
    component.addDie(20);
    component.adjustModifier(2);
    expect(component.totalDiceCount).toBe(1);

    component.clearPool();
    expect(component.totalDiceCount).toBe(0);
    expect(component.modifier()).toBe(0);
  });

  it('should emit customRoll on executeRoll', () => {
    const emitSpy = jest.spyOn(component.customRoll, 'emit');
    component.addDie(20);
    component.executeRoll();

    expect(emitSpy).toHaveBeenCalled();
    expect(component.lastRoll()).not.toBeNull();
  });

  it('should apply rollMode to 1d20 in a mixed pool (e.g. 1d20 + 1d4) and auto-reset rollMode', () => {
    const diceService = TestBed.inject(DiceService);
    const rollD20Spy = jest.spyOn(diceService, 'rollD20');
    component.setRollMode('advantage');
    component.addDie(20);
    component.addDie(4);

    component.executeRoll();

    expect(rollD20Spy).toHaveBeenCalledWith(0, 'advantage');
    expect(component.lastRoll()?.expression).toContain('1d4+1d20 (ADVANTAGE)');
    expect(component.rollMode).toBe('normal');
  });

  it('should emit openChange on close', () => {
    const emitSpy = jest.spyOn(component.openChange, 'emit');
    component.close();
    expect(emitSpy).toHaveBeenCalledWith(false);
  });

  it('triggers 3D dice via showRoll with per-die diceSides for multi-die pools (#197)', () => {
    const toast = TestBed.inject(RollToastService);
    const showRollSpy = jest.spyOn(toast, 'showRoll');
    const showMessageSpy = jest.spyOn(toast, 'showMessage');

    component.addDie(6);
    component.addDie(6);
    component.addDie(8);
    component.adjustModifier(2);
    component.executeRoll();

    expect(showMessageSpy).not.toHaveBeenCalled();
    expect(showRollSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        expression: '2d6+1d8+2',
        rolls: expect.any(Array),
        diceSides: [6, 6, 8],
        modifier: 2,
        rollType: 'custom',
        skipBroadcast: true,
      })
    );
    expect(showRollSpy.mock.calls[0][0].rolls?.length).toBe(3);
  });
});
