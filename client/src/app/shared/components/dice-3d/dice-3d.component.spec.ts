jest.mock(
  'three/examples/jsm/environments/RoomEnvironment.js',
  () => ({ RoomEnvironment: jest.fn() }),
  { virtual: true },
);

jest.mock('cannon-es', () => ({
  Body: jest.fn(),
  ContactMaterial: jest.fn(),
  GSSolver: jest.fn(),
  Material: jest.fn(),
  NaiveBroadphase: jest.fn(),
  Plane: jest.fn(),
  Vec3: jest.fn(),
  World: jest.fn(),
}));

import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SimpleChange } from '@angular/core';
import { Dice3dComponent } from './dice-3d.component';

describe('Dice3dComponent', () => {
  let fixture: ComponentFixture<Dice3dComponent>;
  let component: Dice3dComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Dice3dComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(Dice3dComponent);
    component = fixture.componentInstance;
  });

  it('emits unsupported when WebGL context creation fails in non-GL environments', () => {
    const unsupportedSpy = jest.fn();
    component.unsupported.subscribe(unsupportedSpy);

    fixture.detectChanges();

    expect(unsupportedSpy).toHaveBeenCalledTimes(1);
  });

  it('safely ignores ngOnChanges when renderer failed to initialize and disposes cleanly on destroy', () => {
    fixture.detectChanges();

    expect(() => {
      component.ngOnChanges({
        rollKey: new SimpleChange(0, 1, false),
      });
      fixture.destroy();
    }).not.toThrow();
  });
});
