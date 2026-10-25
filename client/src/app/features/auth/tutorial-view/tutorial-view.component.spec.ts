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
});
