export type AIProvider = 'gemini' | 'anthropic';

export interface AIModelOption {
  id: string;
  label: string;
  provider: AIProvider;
  free_tier: boolean;
}

export interface AISettings {
  preferred_model: string;
  temperature: number;
  available_models: AIModelOption[];
  has_anthropic_key: boolean;
  /** Last 4 characters of the saved key; the key itself is never sent back. */
  anthropic_key_hint: string | null;
}

export interface AISettingsUpdate {
  preferred_model: string;
  temperature: number;
  /** Omit to keep the saved key, '' to remove it, a value to replace it. */
  anthropic_api_key?: string;
}
