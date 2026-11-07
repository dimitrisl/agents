import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';

@Component({
  selector: 'app-dice-3d',
  standalone: true,
  template: '',
})
class MockDice3dComponent {}

jest.mock('../dice-3d/dice-3d.component', () => ({
  Dice3dComponent: MockDice3dComponent,
}));

import { RollToastComponent } from './roll-toast.component';
import { RollToastService } from '../../../core/services/roll-toast.service';

describe('RollToastComponent', () => {
  let component: RollToastComponent;
  let fixture: ComponentFixture<RollToastComponent>;
  let rollService: RollToastService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [RollToastComponent],
      providers: [RollToastService],
    });

    fixture = TestBed.createComponent(RollToastComponent);
    component = fixture.componentInstance;
    rollService = TestBed.inject(RollToastService);
    fixture.detectChanges();
  });

  it('should create RollToastComponent', () => {
    expect(component).toBeTruthy();
  });

  it('renders message-only overlay with .message-only class', () => {
    rollService.showMessage('Action', 'Dodge taken');
    fixture.detectChanges();

    const overlay = fixture.nativeElement.querySelector('.roll-toast-overlay');
    expect(overlay).toBeTruthy();
    expect(overlay.classList.contains('message-only')).toBe(true);
  });

  it('dismisses settled roll on backdrop click', () => {
    const dismissSpy = jest.spyOn(rollService, 'dismiss');
    const roll = {
      title: 'D20 Roll',
      expression: '1d20',
      raw: 15,
      modifier: 2,
      total: 17,
    };
    rollService.showRoll(roll);
    fixture.detectChanges();

    const overlay = fixture.nativeElement.querySelector('.roll-toast-overlay');
    expect(overlay).toBeTruthy();

    const mockEvent = {
      target: overlay,
      currentTarget: overlay,
    } as unknown as MouseEvent;

    component.onBackdropClick(mockEvent, roll);
    expect(dismissSpy).toHaveBeenCalled();
  });

  it('does not dismiss on backdrop click when click target is the card itself', () => {
    const dismissSpy = jest.spyOn(rollService, 'dismiss');
    const roll = {
      title: 'D20 Roll',
      expression: '1d20',
      raw: 15,
      modifier: 2,
      total: 17,
    };
    rollService.showRoll(roll);
    fixture.detectChanges();

    const card = fixture.nativeElement.querySelector('.roll-toast-card');
    const overlay = fixture.nativeElement.querySelector('.roll-toast-overlay');

    const mockEvent = {
      target: card,
      currentTarget: overlay,
    } as unknown as MouseEvent;

    component.onBackdropClick(mockEvent, roll);
    expect(dismissSpy).not.toHaveBeenCalled();
  });
});
