import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { HomebrewPanelComponent } from './homebrew-panel.component';
import { BestiaryService } from '../../../../core/services/bestiary.service';
import { BestiaryMonster } from '../../../../core/models/bestiary.model';
import { ForgeConfirmService } from '../../../../shared/ui';

describe('HomebrewPanelComponent', () => {
  let component: HomebrewPanelComponent;
  let fixture: ComponentFixture<HomebrewPanelComponent>;
  let bestiaryService: BestiaryService;
  let confirmDialog: ForgeConfirmService;

  const mockMonster: BestiaryMonster = {
    id: 'custom_m1',
    name: 'Dire Wolf Alpha',
    edition: '2014',
    origin: 'custom',
    is_public: false,
    size: 'Large',
    type: 'beast',
    alignment: 'unaligned',
    cr: '2',
    cr_numeric: 2,
    ac: 14,
    hp: 37,
    max_hp: 37,
    speed: '50 ft.',
    stats: { str: 17, dex: 15, con: 15, int: 3, wis: 12, cha: 7 },
    traits: [{ name: 'Pack Tactics', description: 'Advantage on attacks when ally nearby' }],
    actions: [{ name: 'Bite', attack_bonus: 5, damage_dice: '2d6+3', damage_type: 'piercing' }],
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HomebrewPanelComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        BestiaryService,
        ForgeConfirmService,
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(HomebrewPanelComponent);
    component = fixture.componentInstance;
    bestiaryService = TestBed.inject(BestiaryService);
    confirmDialog = TestBed.inject(ForgeConfirmService);

    jest.spyOn(bestiaryService, 'getMonsters').mockReturnValue(of([mockMonster]));
    fixture.detectChanges();
  });

  it('should create and load bestiary monsters on init', () => {
    expect(component).toBeTruthy();
    expect(bestiaryService.getMonsters).toHaveBeenCalled();
    expect(component.activeView).toBe('bestiary');
  });

  it('should toggle source filters and reload monsters', () => {
    const spy = jest.spyOn(component, 'loadBestiary');

    component.toggleSource('official');
    expect(component.includeOfficial).toBe(false);
    expect(spy).toHaveBeenCalled();

    component.toggleSource('mine');
    expect(component.includeMine).toBe(false);

    component.toggleSource('community');
    expect(component.includeCommunity).toBe(true);
  });

  it('should format ability modifiers correctly', () => {
    expect(component.abilityMod(10)).toBe('+0');
    expect(component.abilityMod(14)).toBe('+2');
    expect(component.abilityMod(6)).toBe('-2');
    expect(component.abilityMod(undefined)).toBe('+0');
  });

  it('should trigger cloneMonster service call', () => {
    const cloneSpy = jest
      .spyOn(bestiaryService, 'cloneMonster')
      .mockReturnValue(of({ ...mockMonster, id: 'copy_1', name: 'Dire Wolf Alpha (Copy)' }));

    component.cloneMonster(mockMonster);
    expect(cloneSpy).toHaveBeenCalledWith('custom_m1');
  });

  it('should trigger toggleVisibility service call for owned monsters', () => {
    const toggleSpy = jest
      .spyOn(bestiaryService, 'toggleVisibility')
      .mockReturnValue(of({ success: true, is_public: true }));

    component.toggleVisibility(mockMonster);
    expect(toggleSpy).toHaveBeenCalledWith('custom_m1', true);
  });

  it('should ask for confirmation and delete monster', async () => {
    jest.spyOn(confirmDialog, 'ask').mockResolvedValue(true);
    const deleteSpy = jest
      .spyOn(bestiaryService, 'deleteMonster')
      .mockReturnValue(of({ success: true, message: 'Deleted' }));

    await component.deleteMonster(mockMonster);
    expect(deleteSpy).toHaveBeenCalledWith('custom_m1');
  });
});
