import { ComponentFixture, TestBed } from '@angular/core/testing';
import { TutorialViewComponent } from './tutorial-view.component';

describe('TutorialViewComponent', () => {
  let component: TutorialViewComponent;
  let fixture: ComponentFixture<TutorialViewComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TutorialViewComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(TutorialViewComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create and default to role none', () => {
    expect(component).toBeTruthy();
    expect(component.role).toBe('none');
  });

  it('should select player role and reset step to 0', () => {
    jest.spyOn(component.stepChange, 'emit');
    component.selectRole('player');
    expect(component.role).toBe('player');
    expect(component.stepChange.emit).toHaveBeenCalledWith(0);
  });

  it('should navigate through noob-friendly steps', () => {
    component.role = 'player';
    component.step = 0;
    jest.spyOn(component.stepChange, 'emit');

    component.next();
    expect(component.stepChange.emit).toHaveBeenCalledWith(1);

    component.step = 2;
    component.previous();
    expect(component.stepChange.emit).toHaveBeenCalledWith(1);
  });

  it('should emit finish when completing tutorial', () => {
    component.selectRole('player');
    fixture.componentRef.setInput('step', 4);
    fixture.detectChanges();

    jest.spyOn(component.finish, 'emit');
    const compiled = fixture.nativeElement as HTMLElement;
    const buttons = Array.from(compiled.querySelectorAll('button'));
    const finishBtn = buttons.find((b) => b.textContent?.includes('Ξεκίνα') || b.textContent?.includes('Enter'));
    expect(finishBtn).toBeTruthy();
    finishBtn?.click();
    expect(component.finish.emit).toHaveBeenCalled();
  });

  it('should select intro role for What is D&D presentation', () => {
    jest.spyOn(component.roleChange, 'emit');
    jest.spyOn(component.stepChange, 'emit');

    component.selectRole('intro');
    expect(component.role).toBe('intro');
    expect(component.roleChange.emit).toHaveBeenCalledWith('intro');
    expect(component.stepChange.emit).toHaveBeenCalledWith(0);
  });

  it('should render intro presentation slides and allow role selection from slide 5', () => {
    component.selectRole('intro');
    fixture.componentRef.setInput('step', 4);
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Συγχαρητήρια, Μόλις Έμαθες D&D!');

    const playerGuideBtn = Array.from(compiled.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Θέλω να φτιάξω Παίκτη')
    );
    expect(playerGuideBtn).toBeTruthy();
    playerGuideBtn?.click();
    expect(component.role).toBe('player');
  });
});
