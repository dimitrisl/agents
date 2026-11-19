import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActionDockComponent } from './action-dock.component';

describe('ActionDockComponent', () => {
  let fixture: ComponentFixture<ActionDockComponent>;
  let component: ActionDockComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ActionDockComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(ActionDockComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('shows "✦ Level Up" when canLevelUp is true and "★ Max Level (20)" when false', () => {
    const findLevelUpButton = (): HTMLButtonElement | undefined =>
      Array.from(fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>).find(
        (btn) => btn.textContent?.includes('Level Up') || btn.textContent?.includes('Max Level')
      );

    expect(component.canLevelUp).toBe(true);
    let btn = findLevelUpButton();
    expect(btn).toBeTruthy();
    expect(btn!.textContent).toContain('✦ Level Up');
    expect(btn!.disabled).toBe(false);

    fixture.componentRef.setInput('canLevelUp', false);
    fixture.detectChanges();

    btn = findLevelUpButton();
    expect(btn).toBeTruthy();
    expect(btn!.textContent).toContain('★ Max Level (20)');
    expect(btn!.disabled).toBe(true);
  });

  it('locks Short Rest, Long Rest, and Level Up in campaigns unless DM unlocked, and locks all at Exhaustion 6', () => {
    const findBtn = (needle: string): HTMLButtonElement | undefined =>
      Array.from(fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>).find(
        (btn) => btn.textContent?.includes(needle)
      );

    fixture.componentRef.setInput('isInCampaign', true);
    fixture.detectChanges();

    expect(findBtn('Short Rest')?.disabled).toBe(true);
    expect(findBtn('Short Rest')?.textContent).toContain('🔒');
    expect(findBtn('Long Rest')?.disabled).toBe(true);
    expect(findBtn('Long Rest')?.textContent).toContain('🔒');
    expect(findBtn('Level Up')?.disabled).toBe(true);
    expect(findBtn('Level Up')?.textContent).toContain('🔒');

    fixture.componentRef.setInput('shortRestUnlocked', true);
    fixture.componentRef.setInput('longRestUnlocked', true);
    fixture.componentRef.setInput('levelUpUnlocked', true);
    fixture.detectChanges();

    expect(findBtn('Short Rest')?.disabled).toBe(false);
    expect(findBtn('Short Rest')?.textContent).not.toContain('🔒');
    expect(findBtn('Long Rest')?.disabled).toBe(false);
    expect(findBtn('Level Up')?.disabled).toBe(false);

    fixture.componentRef.setInput('isDeceasedByExhaustion', true);
    fixture.detectChanges();
    expect(findBtn('Short Rest')?.disabled).toBe(true);
    expect(findBtn('Long Rest')?.disabled).toBe(true);
    expect(findBtn('Level Up')?.disabled).toBe(true);
  });
});
