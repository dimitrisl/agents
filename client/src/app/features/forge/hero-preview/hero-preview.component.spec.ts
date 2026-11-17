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

  it('falls back to default SVG without mutating hero.char_portrait when image fails to load', () => {
    const heroWithBrokenPortrait: any = {
      char_name: 'Aria',
      char_class: 'Fighter',
      stats: {},
      char_portrait: '/api/v1/portraits/missing.png',
    };
    fixture.componentRef.setInput('hero', heroWithBrokenPortrait);
    fixture.detectChanges();

    const img = fixture.nativeElement.querySelector('img') as HTMLImageElement;
    expect(img.getAttribute('src')).toBe('/api/v1/portraits/missing.png');

    img.dispatchEvent(new Event('error'));
    fixture.detectChanges();

    expect(img.getAttribute('src')?.startsWith('data:image/svg+xml;utf8,')).toBe(true);
    expect(heroWithBrokenPortrait.char_portrait).toBe('/api/v1/portraits/missing.png');
  });
});
