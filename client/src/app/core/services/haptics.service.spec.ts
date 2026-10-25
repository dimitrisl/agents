import { TestBed } from '@angular/core/testing';
import { HapticsService } from './haptics.service';

describe('HapticsService', () => {
  let service: HapticsService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(HapticsService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should safely call methods without throwing', () => {
    expect(() => service.lightTap()).not.toThrow();
    expect(() => service.critSuccess()).not.toThrow();
    expect(() => service.critFail()).not.toThrow();
    expect(() => service.turnAlert()).not.toThrow();
    expect(() => service.damageTaken()).not.toThrow();
  });
});
