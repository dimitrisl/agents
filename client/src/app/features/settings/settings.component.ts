import { Component, OnInit, Optional } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { AIModelOption, AISettings, AISettingsUpdate } from '../../core/models/ai-settings.model';
import { describeHttpError } from '../../core/interceptors/error.interceptor';
import { AuthService } from '../../core/services/auth.service';
import { CharacterStateService } from '../../core/services/character-state.service';
import { RollToastService } from '../../core/services/roll-toast.service';
import { SettingsService } from '../../core/services/settings.service';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeCardComponent,
  ForgeInputDirective,
  ForgePageComponent,
  ForgeSelectDirective,
  ForgeSkeletonComponent,
  ForgeSpinnerComponent,
} from '../../shared/ui';

// Shown until GET /settings/ai answers (or if it fails); mirrors backend AVAILABLE_MODELS.
const DEFAULT_MODEL_OPTIONS: AIModelOption[] = [
  { id: 'gemini-3.5-flash', label: 'Gemini 3.5 Flash (Free)', provider: 'gemini', free_tier: true },
  { id: 'gemini-3.6-flash', label: 'Gemini 3.6 Flash (Fast)', provider: 'gemini', free_tier: false },
  { id: 'gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro (Deep Reasoning)', provider: 'gemini', free_tier: false },
  { id: 'claude-opus-5-5', label: 'Claude Opus 5.5 (Best Quality)', provider: 'anthropic', free_tier: false },
  { id: 'claude-sonnet-5-5', label: 'Claude Sonnet 5.5 (Balanced)', provider: 'anthropic', free_tier: false },
  { id: 'claude-haiku-5-5', label: 'Claude Haiku 5.5 (Cheapest)', provider: 'anthropic', free_tier: false },
];

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeCardComponent,
    ForgeInputDirective,
    ForgePageComponent,
    ForgeSelectDirective,
    ForgeSkeletonComponent,
    ForgeSpinnerComponent,
  ],
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.css',
})
export class SettingsComponent implements OnInit {
  aiTemperature = 0.7;
  preferredModel = 'gemini-3.5-flash';
  modelOptions: AIModelOption[] = DEFAULT_MODEL_OPTIONS;
  saving = false;
  /**
   * Until GET /settings/ai answers the form holds defaults; showing (or saving!)
   * them would flash the wrong model and could overwrite the user's choice.
   */
  loadingSettings = true;

  /** Typed into the key field; never pre-filled, the server only returns a hint. */
  anthropicKeyInput = '';
  hasAnthropicKey = false;
  anthropicKeyHint: string | null = null;
  private removeAnthropicKey = false;

  /** Account security (self-service password change) form state. */
  currentPassword = '';
  newPassword = '';
  confirmPassword = '';
  changingPassword = false;
  passwordError = '';
  passwordSuccess = '';

  constructor(
    public charState: CharacterStateService,
    private rollToast: RollToastService,
    private settingsService: SettingsService,
    @Optional() private authService?: AuthService
  ) {}

  ngOnInit() {
    if (this.mustChangePassword) {
      this.loadingSettings = false;
      return;
    }
    this.loadAISettings();
  }

  private loadAISettings() {
    this.loadingSettings = true;
    this.settingsService.getAISettings().subscribe({
      next: (settings) => {
        this.applySettings(settings);
        this.loadingSettings = false;
      },
      error: (err) => {
        // The interceptor already announced it; fall back to the editable defaults.
        console.error('Failed to load AI settings', err);
        this.loadingSettings = false;
      },
    });
  }

  private applySettings(settings: AISettings) {
    this.preferredModel = settings.preferred_model;
    this.aiTemperature = settings.temperature;
    if (settings.available_models?.length) {
      this.modelOptions = settings.available_models;
    }
    this.hasAnthropicKey = settings.has_anthropic_key;
    this.anthropicKeyHint = settings.anthropic_key_hint;
    this.anthropicKeyInput = '';
    this.removeAnthropicKey = false;
  }

  get geminiModels(): AIModelOption[] {
    return this.modelOptions.filter((m) => m.provider === 'gemini');
  }

  get claudeModels(): AIModelOption[] {
    return this.modelOptions.filter((m) => m.provider === 'anthropic');
  }

  get isClaudeModel(): boolean {
    return this.modelOptions.some((m) => m.id === this.preferredModel && m.provider === 'anthropic');
  }

  /** Marks the saved key for removal on the next save. */
  clearAnthropicKey() {
    this.removeAnthropicKey = true;
    this.hasAnthropicKey = false;
    this.anthropicKeyHint = null;
    this.anthropicKeyInput = '';
  }

  // --- Configuration summary (presentation only, derived from the form state) ---

  get editionShort(): string {
    return this.charState.dndEdition().includes('2024') ? '2024' : '2014';
  }

  get temperatureLabel(): string {
    if (this.aiTemperature <= 0.3) return 'Precise';
    if (this.aiTemperature <= 0.7) return 'Balanced';
    return 'Creative';
  }

  get preferredModelLabel(): string {
    if (this.loadingSettings) return '…';
    const option = this.modelOptions.find((m) => m.id === this.preferredModel);
    // Summary line shows the short name: "Gemini 3.5 Flash (Free)" -> "Gemini 3.5 Flash"
    return option ? option.label.replace(/\s*\(.*\)$/, '') : this.preferredModel;
  }

  get isFreeTierModel(): boolean {
    return this.modelOptions.some((m) => m.id === this.preferredModel && m.free_tier);
  }

  get mustChangePassword(): boolean {
    return Boolean(this.authService?.currentUser()?.must_change_password);
  }

  get isDemoAccount(): boolean {
    return Boolean(this.authService?.currentUser()?.is_demo);
  }

  get hasPassword(): boolean {
    return this.authService?.currentUser()?.has_password !== false;
  }

  get currentUsername(): string {
    return this.authService?.currentUser()?.username || 'Adventurer';
  }

  changePassword() {
    if (this.changingPassword || this.isDemoAccount || !this.authService) return;
    this.passwordError = '';
    this.passwordSuccess = '';

    if (this.hasPassword && !this.currentPassword) {
      this.passwordError = 'Please enter your current password.';
      return;
    }
    if (this.newPassword.length < 8 || this.newPassword.length > 128) {
      this.passwordError = 'New password must be between 8 and 128 characters.';
      return;
    }
    if (this.hasPassword && this.newPassword === this.currentPassword) {
      this.passwordError = 'New password must be different from your current password.';
      return;
    }
    if (this.newPassword !== this.confirmPassword) {
      this.passwordError = 'New password and confirmation do not match.';
      return;
    }

    const payload = this.hasPassword
      ? { current_password: this.currentPassword, new_password: this.newPassword }
      : { new_password: this.newPassword };

    const wasForcedReset = this.mustChangePassword;
    this.changingPassword = true;
    this.authService.changePassword(payload).subscribe({
      next: () => {
        this.changingPassword = false;
        this.currentPassword = '';
        this.newPassword = '';
        this.confirmPassword = '';
        this.passwordSuccess = 'Password updated. All older sessions have been signed out.';
        this.rollToast.showMessage(
          '🔐 PASSWORD UPDATED',
          'Your account password was changed and session rotated.'
        );
        if (wasForcedReset) {
          this.loadAISettings();
        }
      },
      error: (err) => {
        this.changingPassword = false;
        const detail =
          typeof err?.error?.detail === 'string'
            ? err.error.detail
            : err instanceof HttpErrorResponse
              ? describeHttpError(err)?.body
              : undefined;
        this.passwordError = detail || 'Could not update password.';
      },
    });
  }

  onEditionChange(newEdition: string) {
    if (newEdition !== this.charState.dndEdition()) {
      this.charState.toggleEdition();
    }
  }

  saveSettings() {
    const update: AISettingsUpdate = {
      preferred_model: this.preferredModel,
      temperature: this.aiTemperature,
    };
    const typedKey = this.anthropicKeyInput.trim();
    if (typedKey) {
      update.anthropic_api_key = typedKey;
    } else if (this.removeAnthropicKey) {
      update.anthropic_api_key = '';
    }

    this.saving = true;
    this.settingsService
      .updateAISettings(update)
      .subscribe({
        next: (settings) => {
          this.saving = false;
          this.applySettings(settings);
          this.rollToast.showMessage('⚙️ PREFERENCES SAVED', 'Forge settings updated successfully.');
        },
        error: (err) => {
          this.saving = false;
          const detail = err?.error?.detail || 'Could not save AI settings.';
          this.rollToast.showMessage('⚠️ SAVE FAILED', detail);
        },
      });
  }
}
