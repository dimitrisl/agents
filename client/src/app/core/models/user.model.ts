export interface User {
  id: string;
  username: string;
  email?: string;
  name?: string;
  has_completed_tutorial: boolean;
  is_admin?: boolean;
  role?: string;
  must_change_password?: boolean;
  has_password?: boolean;
  is_demo?: boolean;
  auth_providers?: string[];
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface AuthProvidersResponse {
  local: boolean;
  discord: boolean;
}

export interface ChangePasswordPayload {
  current_password?: string;
  new_password: string;
}

export interface DiscordExchangePayload {
  code: string;
}
