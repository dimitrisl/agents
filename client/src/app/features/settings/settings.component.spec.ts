import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { AISettings } from '../../core/models/ai-settings.model';
import { CharacterStateService } from '../../core/services/character-state.service';
import { RollToastService } from '../../core/services/roll-toast.service';
import { SettingsService } from '../../core/services/settings.service';
import { SettingsComponent } from './settings.component';

const SAVED: AISettings = {
  preferred_model: 'claude-sonnet-5-5',
  temperature: 0.7,
  available_models: [
    { id: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash (Fast)', provider: 'gemini', free_tier: false },
    { id: 'claude-sonnet-5-5', label: 'Claude Sonnet 5.5 (Balanced)', provider: 'anthropic', free_tier: false },
  ],
  has_anthropic_key: true,
  anthropic_key_hint: 'abcd',
};

describe('SettingsComponent', () => {
  let fixture: ComponentFixture<SettingsComponent>;
  let component: SettingsComponent;
  let settingsService: { getAISettings: jest.Mock; updateAISettings: jest.Mock };

  beforeEach(async () => {
    settingsService = {
      getAISettings: jest.fn().mockReturnValue(of(SAVED)),
      updateAISettings: jest.fn().mockReturnValue(of(SAVED)),
    };

    await TestBed.configureTestingModule({
      imports: [SettingsComponent],
      providers: [
        { provide: SettingsService, useValue: settingsService },
        { provide: RollToastService, useValue: { showMessage: jest.fn() } },
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
});
