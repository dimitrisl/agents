import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { AISettings } from '../../core/models/ai-settings.model';
import { User } from '../../core/models/user.model';
import { AuthService } from '../../core/services/auth.service';
import { CharacterStateService } from '../../core/services/character-state.service';
import { RollToastService } from '../../core/services/roll-toast.service';
import { SettingsService } from '../../core/services/settings.service';
import { SettingsComponent } from './settings.component';

const SAVED: AISettings = {
  preferred_model: 'claude-sonnet-5-5',
  temperature: 0.7,
  available_models: [
    { id: 'gemini-3.5-flash', label: 'Gemini 3.5 Flash (Free)', provider: 'gemini', free_tier: true },
    { id: 'gemini-3.6-flash', label: 'Gemini 3.6 Flash (Fast)', provider: 'gemini', free_tier: false },
    { id: 'claude-sonnet-5-5', label: 'Claude Sonnet 5.5 (Balanced)', provider: 'anthropic', free_tier: false },
  ],
  has_anthropic_key: true,
  anthropic_key_hint: 'abcd',
};

describe('SettingsComponent', () => {
  let fixture: ComponentFixture<SettingsComponent>;
  let component: SettingsComponent;
  let settingsService: { getAISettings: jest.Mock; updateAISettings: jest.Mock };
  let authService: { currentUser: ReturnType<typeof signal<User | null>>; changePassword: jest.Mock };

  beforeEach(async () => {
    settingsService = {
      getAISettings: jest.fn().mockReturnValue(of(SAVED)),
      updateAISettings: jest.fn().mockReturnValue(of(SAVED)),
    };
    authService = {
      currentUser: signal<User | null>({
        id: 'u1',
        username: 'edrann',
        has_completed_tutorial: true,
        has_password: true,
        must_change_password: false,
        is_demo: false,
      }),
      changePassword: jest.fn().mockReturnValue(
        of({
          access_token: 'rotated',
          token_type: 'bearer',
          user: { id: 'u1', username: 'edrann', has_completed_tutorial: true, has_password: true, must_change_password: false },
        })
      ),
    };

    await TestBed.configureTestingModule({
      imports: [SettingsComponent],
      providers: [
        { provide: SettingsService, useValue: settingsService },
        { provide: RollToastService, useValue: { showMessage: jest.fn() } },
        { provide: AuthService, useValue: authService },
        {
          provide: CharacterStateService,
          useValue: { dndEdition: () => '2014 Edition', toggleEdition: jest.fn() },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(SettingsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('loads the saved Claude model and key hint without the key itself', () => {
    expect(component.preferredModel).toBe('claude-sonnet-5-5');
    expect(component.isClaudeModel).toBe(true);
    expect(component.hasAnthropicKey).toBe(true);
    expect(component.anthropicKeyHint).toBe('abcd');
    expect(component.anthropicKeyInput).toBe('');
  });

  it('stops showing the loading state once the saved settings arrive', () => {
    expect(component.loadingSettings).toBe(false);
    expect(component.preferredModelLabel).toBe('Claude Sonnet 5.5');
  });

  it('keeps the saved key when the field is left empty', () => {
    component.saveSettings();
    const update = settingsService.updateAISettings.mock.calls[0][0];
    expect('anthropic_api_key' in update).toBe(false);
  });

  it('sends a newly typed key', () => {
    component.anthropicKeyInput = '  sk-ant-new  ';
    component.saveSettings();
    expect(settingsService.updateAISettings.mock.calls[0][0].anthropic_api_key).toBe('sk-ant-new');
  });

  it('sends an empty key to remove it', () => {
    component.clearAnthropicKey();
    component.saveSettings();
    expect(settingsService.updateAISettings.mock.calls[0][0].anthropic_api_key).toBe('');
  });

  it('validates password rules before submitting changePassword', () => {
    component.currentPassword = 'oldpassword';
    component.newPassword = 'short';
    component.confirmPassword = 'short';
    component.changePassword();
    expect(component.passwordError).toContain('between 8 and 128');
    expect(authService.changePassword).not.toHaveBeenCalled();

    component.newPassword = 'newStrongPassword1!';
    component.confirmPassword = 'mismatchPassword1!';
    component.changePassword();
    expect(component.passwordError).toContain('do not match');
    expect(authService.changePassword).not.toHaveBeenCalled();
  });

  it('submits password change and clears fields on success', () => {
    component.currentPassword = 'oldpassword';
    component.newPassword = 'newStrongPassword1!';
    component.confirmPassword = 'newStrongPassword1!';
    component.changePassword();

    expect(authService.changePassword).toHaveBeenCalledWith({
      current_password: 'oldpassword',
      new_password: 'newStrongPassword1!',
    });
    expect(component.currentPassword).toBe('');
    expect(component.newPassword).toBe('');
    expect(component.passwordSuccess).toContain('Password updated');
  });

  it('surfaces backend error detail without clearing form on failure', () => {
    authService.changePassword.mockReturnValue(
      throwError(() => ({ error: { detail: 'Current password is incorrect.' } }))
    );
    component.currentPassword = 'wrongpassword';
    component.newPassword = 'newStrongPassword1!';
    component.confirmPassword = 'newStrongPassword1!';
    component.changePassword();

    expect(component.changingPassword).toBe(false);
    expect(component.passwordError).toBe('Current password is incorrect.');
  });

  it('allows Discord-only user without current_password to set a local password', () => {
    authService.currentUser.set({
      id: 'd1',
      username: 'discord_hero',
      has_completed_tutorial: true,
      has_password: false,
    });
    component.newPassword = 'brandNewPassword1!';
    component.confirmPassword = 'brandNewPassword1!';
    component.changePassword();

    expect(authService.changePassword).toHaveBeenCalledWith({
      new_password: 'brandNewPassword1!',
    });
  });

  it('blocks password change for demo accounts in template', () => {
    authService.currentUser.set({
      id: 'local_user_mitsos',
      username: 'mitsos',
      has_completed_tutorial: true,
      is_demo: true,
    });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Demo table accounts');
  });

  it('defers AI settings load during forced reset and loads once password is changed', () => {
    settingsService.getAISettings.mockClear();
    authService.currentUser.set({
      id: 'u1',
      username: 'edrann',
      has_completed_tutorial: true,
      has_password: true,
      must_change_password: true,
    });
    const forcedFixture = TestBed.createComponent(SettingsComponent);
    const forcedComp = forcedFixture.componentInstance;
    forcedFixture.detectChanges();

    expect(settingsService.getAISettings).not.toHaveBeenCalled();
    expect(forcedComp.loadingSettings).toBe(false);

    forcedComp.currentPassword = 'TempPassword1!';
    forcedComp.newPassword = 'NewStrongPassword9!';
    forcedComp.confirmPassword = 'NewStrongPassword9!';
    forcedComp.changePassword();

    expect(settingsService.getAISettings).toHaveBeenCalledTimes(1);
  });
});
