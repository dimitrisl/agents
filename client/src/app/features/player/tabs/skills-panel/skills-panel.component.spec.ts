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
});
