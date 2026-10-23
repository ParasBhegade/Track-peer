jest.mock('react-native', () => ({
  Platform: {
    OS: 'android',
  },
}));

jest.mock('expo-constants', () => ({
  expoConfig: {
    hostUri: undefined,
  },
}));

jest.mock('expo-secure-store', () => {
  const store = new Map<string, string>();
  return {
    getItemAsync: jest.fn(async (key: string) => store.get(key) || null),
    setItemAsync: jest.fn(async (key: string, value: string) => {
      store.set(key, value);
    }),
    deleteItemAsync: jest.fn(async (key: string) => {
      store.delete(key);
    }),
    __store: store,
  };
});

import axios from 'axios';
import * as SecureStore from 'expo-secure-store';
import { saveTokens, getTokens, clearTokens, ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from '../tokenStorage';
import { login, register, logout, refreshSession, restoreSession } from '../auth';
import { apiClient, setAuthToken, getAuthToken, setOnAuthFailure } from '../client';

describe('Token Storage', () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    await clearTokens();
  });

  it('saves and retrieves tokens from SecureStore', async () => {
    await saveTokens({
      accessToken: 'access-123',
      refreshToken: 'refresh-456',
    });

    expect(SecureStore.setItemAsync).toHaveBeenCalledWith(ACCESS_TOKEN_KEY, 'access-123');
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith(REFRESH_TOKEN_KEY, 'refresh-456');

    const tokens = await getTokens();
    expect(tokens).toEqual({
      accessToken: 'access-123',
      refreshToken: 'refresh-456',
    });
  });

  it('returns null when any token is missing in SecureStore', async () => {
    const tokens = await getTokens();
    expect(tokens).toBeNull();
  });

  it('clears stored tokens', async () => {
    await saveTokens({
      accessToken: 'access-123',
      refreshToken: 'refresh-456',
    });

    await clearTokens();

    expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith(ACCESS_TOKEN_KEY);
    expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith(REFRESH_TOKEN_KEY);

    const tokens = await getTokens();
    expect(tokens).toBeNull();
  });
});

describe('Auth API Functions', () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    await clearTokens();
    setAuthToken(null);
  });

  describe('login', () => {
    it('sends login request, stores tokens in SecureStore, and sets memory token', async () => {
      const mockResponse = {
        data: {
          user: {
            id: 'u-1',
            email: 'user@example.com',
            display_name: 'Test User',
            timezone: 'UTC',
            has_password: true,
            google_linked: false,
            created_at: '2026-01-01T00:00:00Z',
          },
          tokens: {
            access_token: 'new-access-token',
            refresh_token: 'new-refresh-token',
            token_type: 'bearer',
            expires_in: 900,
          },
        },
      };

      const postSpy = jest.spyOn(apiClient, 'post').mockResolvedValueOnce(mockResponse as any);

      const result = await login('user@example.com', 'password123');

      expect(postSpy).toHaveBeenCalledWith('/api/v1/auth/login', {
        email: 'user@example.com',
        password: 'password123',
      });
      expect(result).toEqual(mockResponse.data);
      expect(getAuthToken()).toBe('new-access-token');

      const stored = await getTokens();
      expect(stored).toEqual({
        accessToken: 'new-access-token',
        refreshToken: 'new-refresh-token',
      });
    });

    it('propagates error when login fails', async () => {
      const error = new Error('Invalid email or password');
      jest.spyOn(apiClient, 'post').mockRejectedValueOnce(error);

      await expect(login('user@example.com', 'wrongpassword')).rejects.toThrow('Invalid email or password');
      expect(getAuthToken()).toBeNull();
    });
  });

  describe('register', () => {
    it('sends register request with all fields, stores tokens, and sets memory token', async () => {
      const mockResponse = {
        data: {
          user: {
            id: 'u-2',
            email: 'newuser@example.com',
            display_name: 'New Operator',
            timezone: 'Asia/Kolkata',
            has_password: true,
            google_linked: false,
            created_at: '2026-01-01T00:00:00Z',
          },
          tokens: {
            access_token: 'reg-access-token',
            refresh_token: 'reg-refresh-token',
            token_type: 'bearer',
            expires_in: 900,
          },
        },
      };

      const postSpy = jest.spyOn(apiClient, 'post').mockResolvedValueOnce(mockResponse as any);

      const result = await register('newuser@example.com', 'password123', 'New Operator', 'Asia/Kolkata');

      expect(postSpy).toHaveBeenCalledWith('/api/v1/auth/register', {
        email: 'newuser@example.com',
        password: 'password123',
        display_name: 'New Operator',
        timezone: 'Asia/Kolkata',
      });
      expect(result).toEqual(mockResponse.data);
      expect(getAuthToken()).toBe('reg-access-token');

      const stored = await getTokens();
      expect(stored).toEqual({
        accessToken: 'reg-access-token',
        refreshToken: 'reg-refresh-token',
      });
    });

    it('handles registration failure gracefully', async () => {
      const error = new Error('Email already registered');
      jest.spyOn(apiClient, 'post').mockRejectedValueOnce(error);

      await expect(register('taken@example.com', 'password123', 'Name', 'UTC')).rejects.toThrow('Email already registered');
      expect(getAuthToken()).toBeNull();
    });
  });

  describe('logout', () => {
    it('revokes refresh token on server and clears local tokens', async () => {
      await saveTokens({
        accessToken: 'current-acc',
        refreshToken: 'current-ref',
      });
      setAuthToken('current-acc');

      const postSpy = jest.spyOn(apiClient, 'post').mockResolvedValueOnce({ status: 204 } as any);

      await logout();

      expect(postSpy).toHaveBeenCalledWith('/api/v1/auth/logout', {
        refresh_token: 'current-ref',
      });
      expect(getAuthToken()).toBeNull();
      const stored = await getTokens();
      expect(stored).toBeNull();
    });

    it('clears local credentials even if server logout request fails', async () => {
      await saveTokens({
        accessToken: 'current-acc',
        refreshToken: 'current-ref',
      });
      setAuthToken('current-acc');

      jest.spyOn(apiClient, 'post').mockRejectedValueOnce(new Error('Network error'));

      await logout();

      expect(getAuthToken()).toBeNull();
      const stored = await getTokens();
      expect(stored).toBeNull();
    });
  });

  describe('refreshSession', () => {
    it('calls /auth/refresh with refresh_token, updates storage and memory', async () => {
      await saveTokens({
        accessToken: 'old-acc',
        refreshToken: 'old-ref',
      });

      const refreshResponse = {
        data: {
          access_token: 'refreshed-acc',
          refresh_token: 'refreshed-ref',
          token_type: 'bearer',
          expires_in: 900,
        },
      };

      const axiosPostSpy = jest.spyOn(axios, 'post').mockResolvedValueOnce(refreshResponse as any);

      const tokens = await refreshSession();

      expect(axiosPostSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/auth/refresh'),
        { refresh_token: 'old-ref' }
      );
      expect(tokens).toEqual(refreshResponse.data);
      expect(getAuthToken()).toBe('refreshed-acc');

      const stored = await getTokens();
      expect(stored).toEqual({
        accessToken: 'refreshed-acc',
        refreshToken: 'refreshed-ref',
      });
    });

    it('clears credentials and returns null when refresh token is rejected (401)', async () => {
      await saveTokens({
        accessToken: 'old-acc',
        refreshToken: 'revoked-ref',
      });

      const err: any = new Error('Refresh token revoked');
      err.response = { status: 401 };
      jest.spyOn(axios, 'post').mockRejectedValueOnce(err);

      const result = await refreshSession();

      expect(result).toBeNull();
      expect(getAuthToken()).toBeNull();
      const stored = await getTokens();
      expect(stored).toBeNull();
    });
  });

  describe('restoreSession', () => {
    it('returns false when no tokens are stored in SecureStore', async () => {
      const result = await restoreSession();
      expect(result).toBe(false);
      expect(getAuthToken()).toBeNull();
    });

    it('returns true when stored tokens are successfully refreshed on startup', async () => {
      await saveTokens({
        accessToken: 'stored-acc',
        refreshToken: 'stored-ref',
      });

      jest.spyOn(axios, 'post').mockResolvedValueOnce({
        data: {
          access_token: 'new-acc',
          refresh_token: 'new-ref',
          token_type: 'bearer',
          expires_in: 900,
        },
      } as any);

      const result = await restoreSession();

      expect(result).toBe(true);
      expect(getAuthToken()).toBe('new-acc');
    });

    it('clears invalid credentials and returns false when stored refresh token returns 401', async () => {
      await saveTokens({
        accessToken: 'stale-acc',
        refreshToken: 'expired-ref',
      });

      const err: any = new Error('Expired refresh token');
      err.response = { status: 401 };
      jest.spyOn(axios, 'post').mockRejectedValueOnce(err);

      const result = await restoreSession();

      expect(result).toBe(false);
      expect(getAuthToken()).toBeNull();
      const stored = await getTokens();
      expect(stored).toBeNull();
    });

    it('falls back to stored access token when startup refresh fails due to network error', async () => {
      await saveTokens({
        accessToken: 'cached-acc',
        refreshToken: 'valid-ref',
      });

      const networkErr = new Error('Network Error');
      jest.spyOn(axios, 'post').mockRejectedValueOnce(networkErr);

      const result = await restoreSession();

      expect(result).toBe(true);
      expect(getAuthToken()).toBe('cached-acc');
    });
  });
});

describe('Concurrent 401 Token Refresh Handling in Client', () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    await clearTokens();
    setAuthToken('initial-acc');
  });

  it('coalesces multiple concurrent 401s into a single refresh request', async () => {
    await saveTokens({
      accessToken: 'initial-acc',
      refreshToken: 'current-ref',
    });

    let refreshCallCount = 0;
    jest.spyOn(axios, 'post').mockImplementation(async (url: any) => {
      if (typeof url === 'string' && url.includes('/api/v1/auth/refresh')) {
        refreshCallCount++;
        // Small delay to simulate in-flight network request
        await new Promise((res) => setTimeout(res, 50));
        return {
          data: {
            access_token: 'rotated-acc',
            refresh_token: 'rotated-ref',
            token_type: 'bearer',
            expires_in: 900,
          },
        };
      }
      return { data: {} };
    });

    const originalAdapter = apiClient.defaults.adapter;
    const adapterSpy = jest.fn(async (config: any) => ({
      data: { ok: true },
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    }));
    apiClient.defaults.adapter = adapterSpy as any;

    // Trigger response interceptor with concurrent 401 errors
    const interceptor = (apiClient.interceptors.response as any).handlers[0];

    const err1: any = new Error('Unauthorized 1');
    err1.response = { status: 401 };
    err1.config = { url: '/api/v1/occurrences', headers: {} };

    const err2: any = new Error('Unauthorized 2');
    err2.response = { status: 401 };
    err2.config = { url: '/api/v1/stats', headers: {} };

    // Fire two concurrent interceptor calls
    const promise1 = interceptor.rejected(err1);
    const promise2 = interceptor.rejected(err2);

    const [res1, res2] = await Promise.all([promise1, promise2]);

    expect(refreshCallCount).toBe(1);
    expect(adapterSpy).toHaveBeenCalledTimes(2);
    expect(res1.data.ok).toBe(true);
    expect(res2.data.ok).toBe(true);
    expect(getAuthToken()).toBe('rotated-acc');
    const stored = await getTokens();
    expect(stored?.accessToken).toBe('rotated-acc');
    expect(stored?.refreshToken).toBe('rotated-ref');
    apiClient.defaults.adapter = originalAdapter;
  });

  it('calls onAuthFailure when refresh fails on 401 response', async () => {
    await saveTokens({
      accessToken: 'initial-acc',
      refreshToken: 'invalid-ref',
    });

    const onAuthFailureMock = jest.fn();
    setOnAuthFailure(onAuthFailureMock);

    const refreshErr: any = new Error('Token revoked');
    refreshErr.response = { status: 401 };
    jest.spyOn(axios, 'post').mockRejectedValueOnce(refreshErr);

    const err401: any = new Error('Unauthorized');
    err401.response = { status: 401 };
    err401.config = { url: '/api/v1/habits', headers: {} };

    const interceptor = (apiClient.interceptors.response as any).handlers[0];
    await expect(interceptor.rejected(err401)).rejects.toThrow('Token revoked');

    expect(onAuthFailureMock).toHaveBeenCalled();
    expect(getAuthToken()).toBeNull();
    const stored = await getTokens();
    expect(stored).toBeNull();

    setOnAuthFailure(null);
  });
});
