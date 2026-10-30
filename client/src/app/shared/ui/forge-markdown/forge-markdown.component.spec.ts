import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ForgeMarkdownComponent } from './forge-markdown.component';

// Trimmed from a real Edition Comparator answer (note the leading space before "#").
const COMPARISON = ` # Divine Smite: 2014 vs. 2024

## 1. 2014 Version
At 2nd level, when you hit with a **melee weapon attack**, you may expend a spell slot.

## 2. 2024 Version (5.5e)
- Cast it **immediately after hitting** with a melee weapon or Unarmed Strike.
- It uses your **bonus action** and a spell slot.

| Aspect | 2014 | 2024 |
|---|---|---|
| **Type** | Class feature | Spell (*Divine Smite*) |
| **Action cost** | Free | **Bonus action** |
`;

describe('ForgeMarkdownComponent', () => {
  let fixture: ComponentFixture<ForgeMarkdownComponent>;

  function render(markdown: string): HTMLElement {
    fixture = TestBed.createComponent(ForgeMarkdownComponent);
    fixture.componentRef.setInput('content', markdown);
    fixture.detectChanges();
    return fixture.nativeElement.querySelector('.forge-prose');
  }

  it('renders headings, emphasis, lists and tables instead of raw markdown', () => {
    const prose = render(COMPARISON);

    expect(prose.querySelector('h1')?.textContent).toBe('Divine Smite: 2014 vs. 2024');
    expect(prose.querySelectorAll('h2').length).toBe(2);
    expect(prose.querySelector('strong')?.textContent).toBe('melee weapon attack');
    expect(prose.querySelectorAll('li').length).toBe(2);
    expect(prose.querySelectorAll('table th').length).toBe(3);
    expect(prose.querySelectorAll('table tbody tr').length).toBe(2);
    expect(prose.querySelector('td em')?.textContent).toBe('Divine Smite');
    // No markdown syntax left on screen
    expect(prose.textContent).not.toContain('**');
    expect(prose.textContent).not.toContain('|---|');
  });

  it('strips scripts and event handlers the model might emit', () => {
    const prose = render('Hello <img src="x" onerror="alert(1)"> <script>alert(2)</script> [x](javascript:alert(3))');
    expect(prose.querySelector('script')).toBeNull();
    expect(prose.innerHTML).not.toContain('onerror');
    // Angular neutralises the link by prefixing "unsafe:", so it can never run.
    expect(prose.querySelector('a')!.getAttribute('href')).toMatch(/^unsafe:/);
  });

  it('renders nothing for empty content', () => {
    expect(render('').innerHTML).toBe('');
  });
});
