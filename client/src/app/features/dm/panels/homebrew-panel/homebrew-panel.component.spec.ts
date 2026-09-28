import { ComponentFixture, TestBed } from '@angular/core/testing';

import { HomebrewPanelComponent } from './homebrew-panel.component';

describe('HomebrewPanelComponent', () => {
  let component: HomebrewPanelComponent;
  let fixture: ComponentFixture<HomebrewPanelComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HomebrewPanelComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(HomebrewPanelComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
