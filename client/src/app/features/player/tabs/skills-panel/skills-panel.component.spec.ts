import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SkillsPanelComponent } from './skills-panel.component';

const SKILLS: any[] = [
  { name: 'Athletics', ability: 'STR' },
  { name: 'Acrobatics', ability: 'DEX' },
  { name: 'Stealth', ability: 'DEX' },
  { name: 'Arcana', ability: 'INT' },
  { name: 'Insight', ability: 'WIS' },
  { name: 'Persuasion', ability: 'CHA' },
];
const PROFICIENT = new Set(['Stealth', 'Insight']);

describe('SkillsPanelComponent', () => {
  let fixture: ComponentFixture<SkillsPanelComponent>;
  let component: SkillsPanelComponent;

  beforeEach(() => {
    fixture = TestBed.createComponent(SkillsPanelComponent);
    component = fixture.componentInstance;
    component.allSkills = SKILLS;
    component.isProficient = (name) => PROFICIENT.has(name);
    component.getSkillModString = () => '+0';
    component.getAttributeFullName = (attr) => attr;
    fixture.detectChanges();
  });

  const shownSkills = () =>
    Array.from(fixture.nativeElement.querySelectorAll('strong')).map((el: any) => el.textContent.trim());

  it('"Proficient only" opens exactly the groups with a proficient skill and hides untrained ones', () => {
    // Flip the switch the way a player does (the panel is OnPush).
    (fixture.nativeElement.querySelector('forge-toggle [role="switch"]') as HTMLElement).click();
    fixture.detectChanges();

    expect(component.showProficientOnly).toBe(true);
    expect(component.openGroups).toEqual({ STR: false, DEX: true, INT: false, WIS: true, CHA: false });
    expect(shownSkills()).toEqual(['Stealth', 'Insight']);
  });

  it('switching it off restores the groups the player had open', () => {
    component.openGroups = { STR: true, DEX: false, INT: true, WIS: false, CHA: false };
    component.setProficientOnly(true);
    component.setProficientOnly(false);
    expect(component.openGroups).toEqual({ STR: true, DEX: false, INT: true, WIS: false, CHA: false });
  });

  it('Collapse all / Expand all toggles every group', () => {
    expect(component.allOpen).toBe(false); // INT/WIS/CHA start closed
    component.toggleAll();
    expect(component.allOpen).toBe(true);
    component.toggleAll();
    expect(Object.values(component.openGroups).every((open) => !open)).toBe(true);
  });

  it('counts proficient skills per group', () => {
    expect(component.proficientCount('DEX')).toBe(1);
    expect(component.proficientCount('STR')).toBe(0);
  });

  it('renders DIS badges beside skill modifiers when hasCheckDisadvantage is true', () => {
    expect(fixture.nativeElement.textContent).not.toContain('DIS');
    fixture.componentRef.setInput('hasCheckDisadvantage', true);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('DIS');
  });

  it('renders 10+ MIN badges only on proficient skills when hasReliableTalent is true', () => {
    fixture.componentRef.setInput('hasReliableTalent', true);
    fixture.detectChanges();
    const badges = Array.from(fixture.nativeElement.querySelectorAll('forge-badge')).map((b: any) =>
      b.textContent.trim()
    );
    expect(badges.filter((t) => t === '10+ MIN').length).toBe(1); // Only Stealth in open DEX group (Insight WIS is collapsed)
  });

  describe('Mobile Companion compactMobile mode', () => {
    beforeEach(() => {
      fixture.componentRef.setInput('compactMobile', true);
      fixture.componentRef.setInput('passivePerception', 16);
      fixture.componentRef.setInput('passiveInvestigation', 13);
      fixture.componentRef.setInput('passiveInsight', 14);
      fixture.detectChanges();
    });

    it('renders 3-column passives bar and flat alphabetical 1-tap skill list without accordions', () => {
      const el = fixture.nativeElement as HTMLElement;
      expect(el.querySelector('[data-testid="mobile-skills-passives"]')?.textContent).toContain('16');
      expect(el.querySelector('[data-testid="mobile-skills-passives"]')?.textContent).toContain('13');
      expect(el.querySelector('[data-testid="mobile-skills-passives"]')?.textContent).toContain('14');
      expect(shownSkills()).toEqual(['Acrobatics', 'Arcana', 'Athletics', 'Insight', 'Persuasion', 'Stealth']);
    });

    it('filters skills via horizontal filter pills (PROF and ability)', () => {
      const el = fixture.nativeElement as HTMLElement;
      (el.querySelector('[data-testid="mobile-skill-filter-PROF"]') as HTMLButtonElement).click();
      fixture.detectChanges();
      expect(shownSkills()).toEqual(['Insight', 'Stealth']);

      (el.querySelector('[data-testid="mobile-skill-filter-DEX"]') as HTMLButtonElement).click();
      fixture.detectChanges();
      expect(shownSkills()).toEqual(['Acrobatics', 'Stealth']);
    });

    it('emits rollSkill on 1-tap row click and renders Reliable Talent / Exhaustion badges', () => {
      const rollSpy = jest.spyOn(component.rollSkill, 'emit');
      fixture.componentRef.setInput('hasReliableTalent', true);
      fixture.componentRef.setInput('hasCheckDisadvantage', true);
      fixture.detectChanges();

      const el = fixture.nativeElement as HTMLElement;
      const stealthRow = el.querySelector('[data-testid="mobile-skill-row-Stealth"]') as HTMLButtonElement;
      expect(stealthRow.textContent).toContain('10+ MIN');
      expect(stealthRow.textContent).toContain('DIS');

      stealthRow.click();
      expect(rollSpy).toHaveBeenCalledWith({ name: 'Stealth', ability: 'DEX' });
    });
  });
});
