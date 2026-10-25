import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { FaqComponent } from './faq.component';

describe('FaqComponent', () => {
  let component: FaqComponent;
  let fixture: ComponentFixture<FaqComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FaqComponent],
      providers: [provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(FaqComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create and display FAQ items', () => {
    expect(component).toBeTruthy();
    expect(component.faqItems.length).toBeGreaterThan(5);
    expect(component.filteredFaqItems().length).toBe(component.faqItems.length);
  });

  it('should filter items by category', () => {
    component.selectCategory('companion');
    const filtered = component.filteredFaqItems();
    expect(filtered.length).toBeGreaterThan(0);
    expect(filtered.every((i) => i.category === 'companion')).toBe(true);
  });

  it('should search items by keyword in question or tags', () => {
    component.searchQuery.set('concentration');
    const filtered = component.filteredFaqItems();
    expect(filtered.length).toBeGreaterThan(0);
    expect(filtered.some((i) => i.id === 'companion-3')).toBe(true);
  });

  it('should toggle question open/close state and expand/collapse all', () => {
    expect(component.isQuestionOpen('companion-1')).toBe(true);

    component.toggleQuestion('companion-1');
    expect(component.isQuestionOpen('companion-1')).toBe(false);

    component.expandAll();
    expect(component.openQuestions().size).toBe(component.faqItems.length);

    component.collapseAll();
    expect(component.openQuestions().size).toBe(0);
  });
});
