export interface User {
  id: string;
  username: string;
  email?: string;
  name?: string;
  has_completed_tutorial: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}
