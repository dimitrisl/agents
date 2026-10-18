import { TestBed } from '@angular/core/testing';
import { RollToastService, ActiveRollEvent } from './roll-toast.service';

describe('RollToastService', () => {
  let service: RollToastService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(RollToastService);
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should initialize with null activeRoll', () => {
    expect(service.activeRoll()).toBeNull();
  });

  it('should set activeRoll and determine Nat20 correctly', () => {
    const event: ActiveRollEvent = {
      title: 'Attack Roll',
      expression: '1d20+5',
      raw: 20,
      modifier: 5,
      total: 25,
      sides: 20
    };

    service.showRoll(event);
    const active = service.activeRoll();

    expect(active).toBeTruthy();
    expect(active?.isNat20).toBe(true);
    expect(active?.isNat1).toBe(false);
    expect(active?.rolls).toEqual([20]);
  });

  it('should set activeRoll and determine Nat1 correctly', () => {
    const event: ActiveRollEvent = {
      title: 'Attack Roll',
      expression: '1d20+5',
      raw: 1,
      modifier: 5,
      total: 6,
      sides: 20
    };

    service.showRoll(event);
    const active = service.activeRoll();

    expect(active?.isNat20).toBe(false);
    expect(active?.isNat1).toBe(true);
  });

  it('should default sides to 20 if omitted', () => {
    const event: ActiveRollEvent = {
      title: 'Check',
      expression: 'd20',
      raw: 15,
      modifier: 0,
      total: 15
    };

    service.showRoll(event);
    const active = service.activeRoll();
    expect(active?.isNat20).toBe(false);
    expect(active?.isNat1).toBe(false);
  });

  it('should show message and auto-dismiss after 4000ms', () => {
    service.showMessage('Alert', 'Test message');
    expect(service.activeRoll()?.message).toBe('Test message');

    jest.advanceTimersByTime(3999);
    expect(service.activeRoll()).not.toBeNull();

    jest.advanceTimersByTime(1);
    expect(service.activeRoll()).toBeNull();
  });

  it('should auto-dismiss showRoll after MAX_ROLL_LIFETIME (11000ms)', () => {
    service.showRoll({ title: 'Roll', expression: '1d20', raw: 10, modifier: 0, total: 10 });
    expect(service.activeRoll()).not.toBeNull();

    jest.advanceTimersByTime(10999);
    expect(service.activeRoll()).not.toBeNull();

    jest.advanceTimersByTime(1);
    expect(service.activeRoll()).toBeNull();
  });

  it('should shorten the timeout when notifySettled is called', () => {
    service.showRoll({ title: 'Roll', expression: '1d20', raw: 10, modifier: 0, total: 10 });

    // Advance half a second before physics settle
    jest.advanceTimersByTime(500);
    expect(service.activeRoll()).not.toBeNull();

    // Settle physics
    service.notifySettled();

    // 3399ms later, it should still be up
    jest.advanceTimersByTime(3399);
    expect(service.activeRoll()).not.toBeNull();

    // 1ms later, it should be dismissed (3400ms after settle)
    jest.advanceTimersByTime(1);
    expect(service.activeRoll()).toBeNull();
  });

  it('should manually dismiss correctly', () => {
    service.showRoll({ title: 'Roll', expression: '1d20', raw: 10, modifier: 0, total: 10 });
    expect(service.activeRoll()).not.toBeNull();

    service.dismiss();
    expect(service.activeRoll()).toBeNull();

    // Advancing timers should not throw errors or resurrect state
    jest.advanceTimersByTime(20000);
    expect(service.activeRoll()).toBeNull();
  });
});
