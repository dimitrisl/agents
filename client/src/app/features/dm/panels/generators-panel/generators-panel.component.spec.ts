import { GeneratorsPanelComponent } from './generators-panel.component';

describe('GeneratorsPanelComponent', () => {
  let component: GeneratorsPanelComponent;

  beforeEach(() => {
    component = new GeneratorsPanelComponent();
  });

  it('initializes with default values', () => {
    expect(component.partySize).toBe(0);
    expect(component.avgLevel).toBe(1);
    expect(component.difficulty).toBe('Medium');
    expect(component.location).toBe('');
    expect(component.riddleTheme).toBe('');
    expect(component.riddleResult).toBe('');
    expect(component.isGeneratingRiddle).toBe(false);
  });

  it('emits riddleThemeChange when riddle theme changes', () => {
    let emitted: string | undefined;
    component.riddleThemeChange.subscribe((val) => (emitted = val));

    component.riddleThemeChange.emit('Sphinx Crypt');
    expect(emitted).toBe('Sphinx Crypt');
  });

  it('emits generateRiddle when action is triggered', () => {
    let fired = false;
    component.generateRiddle.subscribe(() => (fired = true));

    component.generateRiddle.emit();
    expect(fired).toBe(true);
  });

  it('emits copyRiddle and pinRiddleToNotes', () => {
    let copied = false;
    let pinned = false;
    component.copyRiddle.subscribe(() => (copied = true));
    component.pinRiddleToNotes.subscribe(() => (pinned = true));

    component.copyRiddle.emit();
    component.pinRiddleToNotes.emit();

    expect(copied).toBe(true);
    expect(pinned).toBe(true);
  });
});
