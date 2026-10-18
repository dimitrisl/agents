import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { NO_ERRORS_SCHEMA } from '@angular/core';
import { HeroPreviewComponent } from './hero-preview.component';

describe('HeroPreviewComponent', () => {
  let component: HeroPreviewComponent;
  let fixture: ComponentFixture<HeroPreviewComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HttpClientTestingModule, RouterTestingModule, HeroPreviewComponent],
      schemas: [NO_ERRORS_SCHEMA]
    }).compileComponents();

    fixture = TestBed.createComponent(HeroPreviewComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('hero', { char_name: 'Test', stats: {} });
    fixture.componentRef.setInput('getClassColor', () => '#000');
    fixture.componentRef.setInput('isPrimaryStat', () => false);
    fixture.componentRef.setInput('getModifierString', () => '+0');
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
