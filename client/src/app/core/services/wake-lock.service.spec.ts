import { TestBed } from '@angular/core/testing';
import { WakeLockService } from './wake-lock.service';

describe('WakeLockService', () => {
  let service: WakeLockService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(WakeLockService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
    expect(service.isEnabled()).toBe(false);
    expect(service.isActive()).toBe(false);
  });

  it('should toggle enabled state when toggle is called', async () => {
    expect(service.isEnabled()).toBe(false);
    await service.toggle();
    expect(service.isEnabled()).toBe(true);
    await service.toggle();
    expect(service.isEnabled()).toBe(false);
  });

  it('should disable wake lock cleanly', async () => {
    await service.enable();
    expect(service.isEnabled()).toBe(true);
    await service.disable();
    expect(service.isEnabled()).toBe(false);
    expect(service.isActive()).toBe(false);
  });
});
