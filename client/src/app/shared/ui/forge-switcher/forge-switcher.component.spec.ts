import { ComponentFixture, TestBed, fakeAsync, flush } from '@angular/core/testing';
import { ForgeSwitcherComponent, ForgeSwitcherOption } from './forge-switcher.component';

const OPTIONS: ForgeSwitcherOption[] = [
  { id: 'a', title: 'Edrann', subtitle: 'Lvl 11 Rogue', imageUrl: '/p/edrann.png' },
  { id: 'b', title: 'Valeros', subtitle: 'Lvl 5 Fighter' },
  { id: 'c', title: 'Castle Test', badge: '🏰' },
];

describe('ForgeSwitcherComponent', () => {
  let fixture: ComponentFixture<ForgeSwitcherComponent>;
  let component: ForgeSwitcherComponent;

  beforeEach(() => {
    fixture = TestBed.createComponent(ForgeSwitcherComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('options', OPTIONS);
    fixture.componentRef.setInput('value', 'a');
    fixture.componentRef.setInput('noun', 'hero');
    fixture.componentRef.setInput('listLabel', 'Your heroes');
    fixture.detectChanges();
  });

  afterEach(() => {
    document.querySelectorAll('.cdk-overlay-container').forEach((el) => (el.innerHTML = ''));
  });

  const trigger = () => fixture.nativeElement.querySelector('button') as HTMLButtonElement;
  const options = () => Array.from(document.querySelectorAll('[role="option"]')) as HTMLElement[];

  function openList() {
    trigger().click();
    fixture.detectChanges();
  }

  it('shows the selected option on one line in a button as tall as the header actions', () => {
    expect(trigger().className).toContain('h-11');
    expect(trigger().textContent).toContain('Edrann');
    expect(trigger().textContent).toContain('Lvl 11 Rogue');
    expect(trigger().getAttribute('aria-haspopup')).toBe('listbox');
    expect(trigger().getAttribute('aria-expanded')).toBe('false');
    expect(trigger().getAttribute('aria-label')).toBe('Active hero: Edrann. Change hero');
  });

  it('opens a styled listbox with every option and marks the selected one', fakeAsync(() => {
    openList();
    flush();
    expect(trigger().getAttribute('aria-expanded')).toBe('true');
    expect(options().length).toBe(3);
    expect(options()[0].getAttribute('aria-selected')).toBe('true');
    // No image: the badge, or else the initial
    expect(options()[1].querySelector('img')).toBeNull();
    expect(options()[1].textContent).toContain('V');
    expect(options()[2].textContent).toContain('🏰');
  }));

  it('emits the picked option and closes', fakeAsync(() => {
    const picked: string[] = [];
    component.valueChange.subscribe((id) => picked.push(id));
    openList();
    flush();

    options()[1].click();
    fixture.detectChanges();
    flush();

    expect(picked).toEqual(['b']);
    expect(component.open).toBe(false);
  }));

  it('re-picking the current option just closes without emitting', fakeAsync(() => {
    const picked: string[] = [];
    component.valueChange.subscribe((id) => picked.push(id));
    openList();
    flush();

    options()[0].click();
    fixture.detectChanges();
    flush();

    expect(picked).toEqual([]);
    expect(component.open).toBe(false);
  }));

  it('closes on Escape and returns focus to the trigger', fakeAsync(() => {
    openList();
    flush();
    component.onKeydown(new KeyboardEvent('keydown', { key: 'Escape' }));
    fixture.detectChanges();
    expect(component.open).toBe(false);
    expect(document.activeElement).toBe(trigger());
  }));
});
