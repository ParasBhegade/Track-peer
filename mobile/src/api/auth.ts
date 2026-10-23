import axios from 'axios';
import { apiClient, API_BASE_URL, setAuthToken } from './client';
import { getTokens, saveTokens, clearTokens } from './tokenStorage';

export interface User {
  id: string;
  email: string;
  display_name: string;
  timezone: string;
  goal?: string | null;
  avatar_url?: string | null;
  has_password: boolean;
  google_linked: boolean;
  created_at: string;
}

export interface Tokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthResponse {
  user: User;
  tokens: Tokens;
}

export const login = async (email: string, password: string): Promise<AuthResponse> => {
  const response = await apiClient.post<AuthResponse>('/api/v1/auth/login', {
    email,
    password,
  });

  const { tokens } = response.data;
  if (tokens?.access_token) {
    setAuthToken(tokens.access_token);
    if (tokens.refresh_token) {
      await saveTokens({
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
      });
    }
  }

  return response.data;
};

export const register = async (
  email: string,
  password: string,
  displayName: string,
  timezone: string
): Promise<AuthResponse> => {
  const response = await apiClient.post<AuthResponse>('/api/v1/auth/register', {
    email,
    password,
    display_name: displayName,
    timezone,
  });

  const { tokens } = response.data;
  if (tokens?.access_token) {
    setAuthToken(tokens.access_token);
    if (tokens.refresh_token) {
      await saveTokens({
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
      });
    }
  }

  return response.data;
};

export const logout = async (): Promise<void> => {
  try {
    const stored = await getTokens();
    if (stored?.refreshToken) {
      // Call backend to revoke refresh token
      await apiClient.post('/api/v1/auth/logout', {
        refresh_token: stored.refreshToken,
      });
    }
  } catch {
    // Ignore server/network errors during logout so local cleanup always succeeds
  } finally {
    setAuthToken(null);
    await clearTokens();
  }
};

export const refreshSession = async (): Promise<Tokens | null> => {
  const stored = await getTokens();
  if (!stored?.refreshToken) {
    setAuthToken(null);
    await clearTokens();
    return null;
  }

  try {
    const response = await axios.post<Tokens>(`${API_BASE_URL}/api/v1/auth/refresh`, {
      refresh_token: stored.refreshToken,
    });

    const newTokens = response.data;
    setAuthToken(newTokens.access_token);
    await saveTokens({
      accessToken: newTokens.access_token,
      refreshToken: newTokens.refresh_token,
    });

    return newTokens;
  } catch (error: any) {
    if (error?.response?.status === 401) {
      setAuthToken(null);
      await clearTokens();
      return null;
    }
    throw error;
  }
};

export const restoreSession = async (): Promise<boolean> => {
  try {
    const stored = await getTokens();
    if (!stored?.refreshToken) {
      setAuthToken(null);
      await clearTokens();
      return false;
    }

    try {
      const refreshed = await refreshSession();
      return refreshed !== null;
    } catch (err: any) {
      if (err?.response?.status === 401) {
        setAuthToken(null);
        await clearTokens();
        return false;
      }
      // If network failure occurs during startup, fallback to stored access token if available
      if (stored.accessToken) {
        setAuthToken(stored.accessToken);
        return true;
      }
      return false;
    }
  } catch {
    setAuthToken(null);
    await clearTokens();
    return false;
  }
};
