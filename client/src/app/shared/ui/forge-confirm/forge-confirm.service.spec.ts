import { ApplicationRef } from '@angular/core';
import { TestBed, fakeAsync, flush } from '@angular/core/testing';
import { ForgeConfirmService } from './forge-confirm.service';

describe('ForgeConfirmService', () => {
  let service: ForgeConfirmService;
  let appRef: ApplicationRef;

  beforeEach(() => {
    service = TestBed.inject(ForgeConfirmService);
    appRef = TestBed.inject(ApplicationRef);
  });

  afterEach(() => {
    document.querySelectorAll('.cdk-overlay-container').forEach((el) => (el.innerHTML = ''));
  });

  function open(tone: 'danger' | 'default' = 'danger') {
    let result: boolean | undefined;
    service
      .ask({ title: 'Delete hero?', message: 'Gone for good.', confirmLabel: 'Delete hero', tone })
      .then((r) => (result = r));
    appRef.tick();
    const dialog = document.querySelector('forge-confirm-dialog') as HTMLElement;
    const [cancel, confirm] = Array.from(dialog.querySelectorAll('button'));
    return { dialog, cancel, confirm, result: () => result };
  }

  it('renders an accessible alert dialog with the given text', fakeAsync(() => {
    const { dialog, confirm } = open();
    expect(dialog.getAttribute('role')).toBe('alertdialog');
    expect(dialog.textContent).toContain('Delete hero?');
    expect(dialog.textContent).toContain('Gone for good.');
    expect(confirm.textContent).toContain('Delete hero');
    // Destructive: red confirm button, and Cancel is the initially focused one.
    expect(confirm.className).toContain('text-red');
    expect(dialog.querySelectorAll('button')[0].hasAttribute('cdkfocusinitial')).toBe(true);
    flush();
  }));

  it('resolves true on confirm', fakeAsync(() => {
    const { confirm, result } = open();
    confirm.click();
    flush();
    expect(result()).toBe(true);
  }));

  it('resolves false on cancel', fakeAsync(() => {
    const { cancel, result } = open();
    cancel.click();
    flush();
    expect(result()).toBe(false);
  }));
});
