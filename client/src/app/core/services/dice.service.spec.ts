import { TestBed } from '@angular/core/testing';

import { DiceService } from './dice.service';

/**
 * Smoke test for the harness itself: it proves Jest boots and that an Angular
 * service can be pulled out of the TestBed injector. The dice rules are covered
 * by their own ticket — keep behavioural tests out of here.
 */
describe('DiceService', () => {
  let service: DiceService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(DiceService);
  });

  it('is provided through the injector', () => {
    expect(service).toBeInstanceOf(DiceService);
  });

  it('signs a positive modifier', () => {
    expect(service.signed(3)).toBe('+3');
  });
});
