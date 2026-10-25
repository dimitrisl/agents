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

  it('should create without an "all" category and default to the expanded DM axis', () => {
    expect(component).toBeTruthy();
    expect(component.categories.some((c) => c.id === 'all')).toBe(false);
    expect(component.selectedCategory()).toBe('dm');
    expect(component.filteredFaqItems().length).toBe(7);
    expect(component.filteredFaqItems().every((i) => i.category === 'dm')).toBe(true);
  });

  it('should filter items by category (including player, dm, and companion axes)', () => {
    component.selectCategory('player');
    expect(component.filteredFaqItems().length).toBe(3);
    expect(component.filteredFaqItems().every((i) => i.category === 'player')).toBe(true);

    component.selectCategory('dm');
    expect(component.filteredFaqItems().length).toBe(7);
    expect(component.filteredFaqItems().every((i) => i.category === 'dm')).toBe(true);

    component.selectCategory('companion');
    const filtered = component.filteredFaqItems();
    expect(filtered.length).toBe(2);
    expect(filtered.every((i) => i.category === 'companion')).toBe(true);
  });

  it('should search items across all categories by keyword in question or tags', () => {
    component.selectCategory('dm');
    component.searchQuery.set('concentration');
    const filtered = component.filteredFaqItems();
    expect(filtered.length).toBeGreaterThan(0);
    expect(filtered.some((i) => i.id === 'companion-2')).toBe(true);
  });

  it('should toggle question open/close state and expand/collapse all filtered items', () => {
    expect(component.isQuestionOpen('dm-1')).toBe(true);

    component.toggleQuestion('dm-1');
    expect(component.isQuestionOpen('dm-1')).toBe(false);

    component.expandAll();
    expect(component.openQuestions().size).toBe(component.filteredFaqItems().length);

    component.collapseAll();
    expect(component.openQuestions().size).toBe(0);
  });
});
