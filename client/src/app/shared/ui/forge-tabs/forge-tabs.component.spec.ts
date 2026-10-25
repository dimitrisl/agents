import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ForgeTabsComponent } from './forge-tabs.component';

describe('ForgeTabsComponent', () => {
  let component: ForgeTabsComponent;
  let fixture: ComponentFixture<ForgeTabsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ForgeTabsComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(ForgeTabsComponent);
    component = fixture.componentInstance;
    component.tabs = [
      { id: 'tab1', label: 'Tab 1' },
      { id: 'tab2', label: 'Tab 2' },
      { id: 'tab3', label: 'Tab 3' },
      { id: 'tab4', label: 'Tab 4' },
    ];
    component.activeId = 'tab1';
  });

  it('should create and render tabs with default flex layout', () => {
    fixture.detectChanges();
    expect(component).toBeTruthy();
    expect(component.tablistClasses).toContain('flex');
    expect(component.tablistClasses).not.toContain('grid');
  });

  it('should support 2-column mobile grid layout when mobileColumns is 2', () => {
    component.mobileColumns = 2;
    fixture.detectChanges();
    expect(component.tablistClasses).toContain('grid grid-cols-2');
    expect(component.tablistClasses).toContain('sm:flex');
    expect(component.buttonBaseClasses).toContain('w-full');
  });

  it('should emit activeIdChange when selecting a tab', () => {
    fixture.detectChanges();
    jest.spyOn(component.activeIdChange, 'emit');

    component.selectTab({ id: 'tab3', label: 'Tab 3' });
    expect(component.activeIdChange.emit).toHaveBeenCalledWith('tab3');
  });
});
