import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { HomebrewForgeModalComponent } from './homebrew-forge-modal.component';

describe('HomebrewForgeModalComponent', () => {
  let component: HomebrewForgeModalComponent;
  let fixture: ComponentFixture<HomebrewForgeModalComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HomebrewForgeModalComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()]
    })
    .compileComponents();

    fixture = TestBed.createComponent(HomebrewForgeModalComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('correctly parses and saves monster with custom actions and traits text', () => {
    const saveSpy = jest.spyOn(component.homebrewService, 'saveHomebrew').mockReturnValue({
      subscribe: (observer: any) => {
        observer.next({});
        return { unsubscribe: () => {} };
      },
    } as any);

    component.campaignName = 'Underdark';
    component.selectedType = 'monster';
    component.formData = {
      name: 'Cave Stalker',
      size: 'Medium',
      type: 'aberration',
      alignment: 'neutral evil',
      cr: '3',
      ac: 14,
      hp: 45,
      speed: '40 ft., climb 30 ft.',
      stats: { str: 14, dex: 16, con: 12, int: 8, wis: 12, cha: 6 },
      actions_text: 'Bite: +5 to hit, 1d8+3 piercing\nTail Sting: +5 to hit, 1d6 poison',
      traits_text: 'Spider Climb: Can climb difficult surfaces without an ability check.',
      senses: 'Darkvision 60 ft.',
      languages: 'Undercommon',
    };

    component.save();

    expect(saveSpy).toHaveBeenCalledWith(
      'Underdark',
      expect.objectContaining({
        name: 'Cave Stalker',
        homebrew_type: 'monster',
        ac: 14,
        hp: 45,
        actions: [
          { name: 'Bite', description: '+5 to hit, 1d8+3 piercing' },
          { name: 'Tail Sting', description: '+5 to hit, 1d6 poison' },
        ],
        traits: [
          { name: 'Spider Climb', description: 'Can climb difficult surfaces without an ability check.' },
        ],
        senses: 'Darkvision 60 ft.',
        languages: 'Undercommon',
      })
    );
    const savedPayload = saveSpy.mock.calls[0][1];
    expect(savedPayload['actions_text']).toBeUndefined();
    expect(savedPayload['traits_text']).toBeUndefined();
  });

  it('handles null AI response gracefully and resets isForging', () => {
    jest.spyOn(component.homebrewService, 'forgeWithAI').mockReturnValue({
      subscribe: (observer: any) => {
        observer.next(null);
        return { unsubscribe: () => {} };
      },
    } as any);
    const toastSpy = jest.spyOn(component.rollToast, 'showMessage');

    component.campaignName = 'Underdark';
    component.aiPrompt = 'A shadowy blade';
    component.forgeWithAI();

    expect(component.isForging).toBe(false);
    expect(toastSpy).toHaveBeenCalledWith(
      '❌ FORGE FAILED',
      expect.stringContaining('empty or invalid')
    );
  });

  it('clears stale monster actions when actions_text is emptied and omits monster fields when saving weapon', () => {
    const saveSpy = jest.spyOn(component.homebrewService, 'saveHomebrew').mockReturnValue({
      subscribe: (observer: any) => {
        observer.next({});
        return { unsubscribe: () => {} };
      },
    } as any);

    component.campaignName = 'Underdark';
    component.selectedType = 'monster';
    component.formData = {
      ...component.formData,
      name: 'Shadow Hound',
      actions: [{ name: 'Stale Bite', description: 'Old' }],
      actions_text: '   ',
      traits_text: '',
    };

    component.save();
    expect(saveSpy).toHaveBeenLastCalledWith(
      'Underdark',
      expect.objectContaining({
        name: 'Shadow Hound',
        homebrew_type: 'monster',
        actions: [],
        traits: [],
      })
    );

    component.selectedType = 'weapon';
    component.formData = {
      ...component.formData,
      name: 'Frostbrand',
      damage_dice: '1d8',
      attack_bonus: '+1',
    };
    component.save();

    const weaponPayload = saveSpy.mock.calls[1][1];
    expect(weaponPayload['homebrew_type']).toBe('weapon');
    expect(weaponPayload['damage_dice']).toBe('1d8');
    expect(weaponPayload['ac']).toBeUndefined();
    expect(weaponPayload['stats']).toBeUndefined();
    expect(weaponPayload['actions_text']).toBeUndefined();
  });
});
