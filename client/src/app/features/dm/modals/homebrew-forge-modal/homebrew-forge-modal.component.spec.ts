import { ComponentFixture, TestBed } from '@angular/core/testing';

import { HomebrewForgeModalComponent } from './homebrew-forge-modal.component';

describe('HomebrewForgeModalComponent', () => {
  let component: HomebrewForgeModalComponent;
  let fixture: ComponentFixture<HomebrewForgeModalComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HomebrewForgeModalComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(HomebrewForgeModalComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
