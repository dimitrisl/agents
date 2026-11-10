import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { of, throwError } from 'rxjs';

import { HomebrewPanelComponent } from './homebrew-panel.component';
import { BestiaryService } from '../../../../core/services/bestiary.service';
import { BestiaryMonster } from '../../../../core/models/bestiary.model';
import { ForgeConfirmService } from '../../../../shared/ui';
import { AuthService } from '../../../../core/services/auth.service';
import { RollToastService } from '../../../../core/services/roll-toast.service';

describe('HomebrewPanelComponent Adversarial & Edge Case Tests', () => {
  let component: HomebrewPanelComponent;
  let fixture: ComponentFixture<HomebrewPanelComponent>;
  let bestiaryService: BestiaryService;
  let confirmDialog: ForgeConfirmService;
  let authService: AuthService;
  let rollToast: RollToastService;

  const srdMonster: BestiaryMonster = {
    id: 'srd_ancient_gold_dragon',
    name: 'Ancient Gold Dragon',
    edition: '2014',
    origin: 'official',
    is_public: true,
    size: 'Gargantuan',
    type: 'dragon',
    alignment: 'lawful good',
    cr: '24',
    cr_numeric: 24,
    ac: 22,
    hp: 546,
    speed: '40 ft., fly 80 ft., swim 40 ft.',
  };

  const customMonsterOwned: BestiaryMonster = {
    id: 'custom_m_owned',
    name: 'Phyrexian Dreadnought',
    edition: '2024',
    origin: 'custom',
    creator_dm_id: 'dm_test_user_1',
    is_public: false,
    size: 'Huge',
    type: 'construct',
    alignment: 'lawful evil',
    cr: '12',
    cr_numeric: 12,
    ac: 18,
    hp: 190,
  };

  const customMonsterOther: BestiaryMonster = {
    id: 'custom_m_other',
    name: 'Other DM Chimera',
    edition: '2014',
    origin: 'custom',
    creator_dm_id: 'dm_other_user_2',
    is_public: true,
    size: 'Large',
    type: 'monstrosity',
    alignment: 'chaotic evil',
    cr: '6',
    cr_numeric: 6,
    ac: 14,
    hp: 114,
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HomebrewPanelComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        BestiaryService,
        ForgeConfirmService,
        RollToastService,
        {
          provide: AuthService,
          useValue: {
            currentUser: () => ({ id: 'dm_test_user_1', username: 'TestDM', role: 'dm' }),
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(HomebrewPanelComponent);
    component = fixture.componentInstance;
    bestiaryService = TestBed.inject(BestiaryService);
    confirmDialog = TestBed.inject(ForgeConfirmService);
    authService = TestBed.inject(AuthService);
    rollToast = TestBed.inject(RollToastService);

    jest.spyOn(bestiaryService, 'getMonsters').mockReturnValue(of([srdMonster, customMonsterOwned]));
    fixture.detectChanges();
  });

  describe('SRD Immutability Enforcement in UI', () => {
    it('isOfficial identifies SRD monsters by id prefix or origin', () => {
      expect(component.isOfficial(srdMonster)).toBe(true);
      expect(component.isOfficial(customMonsterOwned)).toBe(false);
      expect(component.isOfficial(customMonsterOther)).toBe(false);
    });

    it('isOwner correctly detects ownership based on auth currentUser', () => {
      // SRD monster can never be owned
      expect(component.isOwner(srdMonster)).toBe(false);
      // Owned custom monster
      expect(component.isOwner(customMonsterOwned)).toBe(true);
      // Other DM custom monster
      expect(component.isOwner(customMonsterOther)).toBe(false);
    });

    it('toggleVisibility cleanly aborts and never calls service for official monsters', () => {
      const toggleSpy = jest.spyOn(bestiaryService, 'toggleVisibility');
      component.toggleVisibility(srdMonster);
      expect(toggleSpy).not.toHaveBeenCalled();
    });

    it('deleteMonster cleanly aborts and never opens confirm dialog for official monsters', async () => {
      const askSpy = jest.spyOn(confirmDialog, 'ask');
      const deleteSpy = jest.spyOn(bestiaryService, 'deleteMonster');
      await component.deleteMonster(srdMonster);
      expect(askSpy).not.toHaveBeenCalled();
      expect(deleteSpy).not.toHaveBeenCalled();
    });
  });

  describe('Source Filtering Combinations', () => {
    it('defaults source chips to Official=true, Mine=true, 3rd-Party=false', () => {
      expect(component.includeOfficial).toBe(true);
      expect(component.includeMine).toBe(true);
      expect(component.includeCommunity).toBe(false);
    });

    it('disabling all source chips passes all false to getMonsters', () => {
      const getMonstersSpy = jest.spyOn(bestiaryService, 'getMonsters');
      component.toggleSource('official'); // becomes false
      component.toggleSource('mine');     // becomes false

      expect(component.includeOfficial).toBe(false);
      expect(component.includeMine).toBe(false);
      expect(component.includeCommunity).toBe(false);

      expect(getMonstersSpy).toHaveBeenLastCalledWith(
        expect.objectContaining({
          include_official: false,
          include_mine: false,
          include_community: false,
        })
      );
    });

    it('enabling 3rd-Party passes include_community: true', () => {
      const getMonstersSpy = jest.spyOn(bestiaryService, 'getMonsters');
      component.toggleSource('community');
      expect(component.includeCommunity).toBe(true);
      expect(getMonstersSpy).toHaveBeenLastCalledWith(
        expect.objectContaining({
          include_community: true,
        })
      );
    });
  });

  describe('Error Handling and Toast Notifications', () => {
    it('shows toast when clone fails', () => {
      jest.spyOn(bestiaryService, 'cloneMonster').mockReturnValue(throwError(() => ({ error: { detail: 'Server down' } })));
      const toastSpy = jest.spyOn(rollToast, 'showMessage');

      component.cloneMonster(srdMonster);
      expect(toastSpy).toHaveBeenCalledWith('⚠️ CLONE FAILED', 'Server down');
    });

    it('shows toast when visibility toggle fails', () => {
      jest.spyOn(bestiaryService, 'toggleVisibility').mockReturnValue(throwError(() => ({ error: { detail: 'Forbidden' } })));
      const toastSpy = jest.spyOn(rollToast, 'showMessage');

      component.toggleVisibility(customMonsterOwned);
      expect(toastSpy).toHaveBeenCalledWith('⚠️ UPDATE FAILED', 'Forbidden');
    });

    it('shows toast when delete fails after user confirmation', async () => {
      jest.spyOn(confirmDialog, 'ask').mockResolvedValue(true);
      jest.spyOn(bestiaryService, 'deleteMonster').mockReturnValue(throwError(() => ({ error: { detail: 'Cannot delete' } })));
      const toastSpy = jest.spyOn(rollToast, 'showMessage');

      await component.deleteMonster(customMonsterOwned);
      expect(toastSpy).toHaveBeenCalledWith('⚠️ DELETE FAILED', 'Cannot delete');
    });

    it('does not delete if user cancels confirmation dialog', async () => {
      jest.spyOn(confirmDialog, 'ask').mockResolvedValue(false);
      const deleteSpy = jest.spyOn(bestiaryService, 'deleteMonster');

      await component.deleteMonster(customMonsterOwned);
      expect(deleteSpy).not.toHaveBeenCalled();
    });
  });
});
