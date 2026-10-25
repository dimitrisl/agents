import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Component, ViewChild, TemplateRef } from '@angular/core';
import { ChoiceViewComponent } from './choice-view.component';

@Component({
  standalone: true,
  imports: [ChoiceViewComponent],
  template: `
    <ng-template #dummyLogo><div>Logo</div></ng-template>
    <app-choice-view
      [logoTemplate]="dummyLogo"
      (chooseTutorial)="onTutorial()"
      (chooseAuth)="onAuth()"
      (chooseWhatIsDnd)="onWhatIsDnd()"
    />
  `,
})
class TestHostComponent {
  @ViewChild('dummyLogo', { static: true }) dummyLogo!: TemplateRef<unknown>;
  onTutorial = jest.fn();
  onAuth = jest.fn();
  onWhatIsDnd = jest.fn();
}

describe('ChoiceViewComponent', () => {
  let fixture: ComponentFixture<TestHostComponent>;
  let host: TestHostComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TestHostComponent, ChoiceViewComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(TestHostComponent);
    host = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should emit chooseTutorial when clicking I\'m New Here!', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const buttons = Array.from(compiled.querySelectorAll('button'));
    const btn = buttons.find((b) => b.textContent?.includes("I'm New Here!"));
    expect(btn).toBeTruthy();
    btn?.click();
    expect(host.onTutorial).toHaveBeenCalledTimes(1);
  });

  it('should emit chooseAuth when clicking Seasoned Adventurer', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const buttons = Array.from(compiled.querySelectorAll('button'));
    const btn = buttons.find((b) => b.textContent?.includes('Seasoned Adventurer'));
    expect(btn).toBeTruthy();
    btn?.click();
    expect(host.onAuth).toHaveBeenCalledTimes(1);
  });

  it('should emit chooseWhatIsDnd when clicking What is D&D?', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const buttons = Array.from(compiled.querySelectorAll('button'));
    const btn = buttons.find((b) => b.textContent?.includes('What is D&D?'));
    expect(btn).toBeTruthy();
    btn?.click();
    expect(host.onWhatIsDnd).toHaveBeenCalledTimes(1);
  });
});
