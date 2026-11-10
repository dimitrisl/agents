import { ComponentFixture, TestBed } from '@angular/core/testing';
import { GeneratorsPanelComponent } from './generators-panel.component';

describe('GeneratorsPanelComponent Adversarial & Edge Case Tests', () => {
  let component: GeneratorsPanelComponent;
  let fixture: ComponentFixture<GeneratorsPanelComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GeneratorsPanelComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(GeneratorsPanelComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  describe('Riddle Generator Template State and Action Invariants', () => {
    it('disables Generate button when riddleTheme is empty', () => {
      component.riddleTheme = '';
      component.isGeneratingRiddle = false;
      fixture.detectChanges();

      const el: HTMLElement = fixture.nativeElement;
      const btn = el.querySelector('#dm-riddle-heading')?.parentElement?.parentElement?.querySelector('button[type="button"]');
      expect(btn).toBeTruthy();
      expect((btn as HTMLButtonElement).disabled).toBe(true);
    });

    it('disables Generate button and shows "⏳ Forging..." when isGeneratingRiddle is true', () => {
      component.riddleTheme = 'Sphinx Crypt';
      component.isGeneratingRiddle = true;
      fixture.detectChanges();

      const el: HTMLElement = fixture.nativeElement;
      const btn = el.querySelector('#dm-riddle-heading')?.parentElement?.parentElement?.querySelector('button[type="button"]');
      expect(btn).toBeTruthy();
      expect((btn as HTMLButtonElement).disabled).toBe(true);
      expect(btn?.textContent?.trim()).toContain('⏳ Forging...');
    });

    it('enables Generate button when riddleTheme has text and isGeneratingRiddle is false', () => {
      component.riddleTheme = 'Sunken Foundry';
      component.isGeneratingRiddle = false;
      fixture.detectChanges();

      const el: HTMLElement = fixture.nativeElement;
      const btn = el.querySelector('#dm-riddle-heading')?.parentElement?.parentElement?.querySelector('button[type="button"]');
      expect(btn).toBeTruthy();
      expect((btn as HTMLButtonElement).disabled).toBe(false);
      expect(btn?.textContent?.trim()).toContain('Generate Riddle / Trap');
    });

    it('does not display result box or action buttons when riddleResult is empty', () => {
      component.riddleResult = '';
      fixture.detectChanges();

      const el: HTMLElement = fixture.nativeElement;
      const riddleSection = el.querySelector('section[aria-labelledby="dm-riddle-heading"]');
      const resultBox = riddleSection?.querySelector('.p-4 > .bg-tile');
      expect(resultBox).toBeNull();
    });

    it('displays markdown component and Copy/Pin buttons when riddleResult is populated', () => {
      component.riddleResult = '### Riddle\n\nI speak without a tongue.';
      fixture.detectChanges();

      const el: HTMLElement = fixture.nativeElement;
      const riddleSection = el.querySelector('section[aria-labelledby="dm-riddle-heading"]');
      const resultBox = riddleSection?.querySelector('.p-4 > .bg-tile');
      expect(resultBox).toBeTruthy();

      const buttons = resultBox?.querySelectorAll('button');
      expect(buttons?.length).toBe(2);
      expect(buttons?.[0]?.textContent?.trim()).toContain('📋 Copy');
      expect(buttons?.[1]?.textContent?.trim()).toContain('📌 Pin to Notes');

      const markdown = resultBox?.querySelector('forge-markdown');
      expect(markdown).toBeTruthy();
    });
  });
});
