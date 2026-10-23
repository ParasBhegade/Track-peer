import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { Platform } from 'react-native';
import Constants from 'expo-constants';
import { getTokens, saveTokens, clearTokens } from './tokenStorage';

// Use 10.0.2.2 for Android emulator to host machine, localhost for iOS simulator/web
export const resolveApiUrl = (): string => {
  if (process.env.EXPO_PUBLIC_API_URL) {
    return process.env.EXPO_PUBLIC_API_URL;
  }

  let devUrl = Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000';

  if (typeof __DEV__ !== 'undefined' && __DEV__) {
    // Expo development server host (e.g. "192.168.42.252:8081")
    const hostUri = Constants.expoConfig?.hostUri;
    if (hostUri) {
      const host = hostUri.split(':')[0];
      if (host && host !== '127.0.0.1' && host !== 'localhost') {
        devUrl = `http://${host}:8000`;
      }
    }
  }
  
  return devUrl;
};

export const API_BASE_URL = resolveApiUrl();

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

let currentToken: string | null = null;
let onAuthFailureCallback: (() => void) | null = null;

export const setOnAuthFailure = (callback: (() => void) | null) => {
  onAuthFailureCallback = callback;
};

export const setAuthToken = (token: string | null) => {
  currentToken = token;
  if (token) {
    apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  } else {
    delete apiClient.defaults.headers.common['Authorization'];
  }
};

export const getAuthToken = () => currentToken;

// Queue mechanism for handling concurrent 401s
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: any) => void;
}> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((promise) => {
    if (error) {
      promise.reject(error);
    } else if (token) {
      promise.resolve(token);
    }
  });
  failedQueue = [];
};

// Request interceptor to attach bearer token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (currentToken && !config.headers.Authorization) {
      config.headers.Authorization = `Bearer ${currentToken}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to handle 401 and refresh token rotation
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;

    if (!originalRequest || !error.response || error.response.status !== 401) {
      return Promise.reject(error);
    }

    // Bypass token refresh on auth endpoints to prevent loops
    const url = originalRequest.url || '';
    if (
      url.includes('/api/v1/auth/login') ||
      url.includes('/api/v1/auth/register') ||
      url.includes('/api/v1/auth/refresh') ||
      url.includes('/api/v1/auth/logout')
    ) {
      return Promise.reject(error);
    }

    // If already retried once, do not retry again
    if (originalRequest._retry) {
      return Promise.reject(error);
    }

    if (isRefreshing) {
      // Queue this request until the ongoing refresh completes
      return new Promise<string>((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      })
        .then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return apiClient(originalRequest);
        })
        .catch((err) => Promise.reject(err));
    }

    originalRequest._retry = true;
    isRefreshing = true;

    try {
      const stored = await getTokens();
      if (!stored?.refreshToken) {
        setAuthToken(null);
        await clearTokens();
        onAuthFailureCallback?.();
        processQueue(error, null);
        return Promise.reject(error);
      }

      // Perform refresh call directly using axios to bypass client interceptors
      const refreshResponse = await axios.post(`${API_BASE_URL}/api/v1/auth/refresh`, {
        refresh_token: stored.refreshToken,
      });

      const { access_token, refresh_token } = refreshResponse.data;

      setAuthToken(access_token);
      await saveTokens({
        accessToken: access_token,
        refreshToken: refresh_token,
      });

      processQueue(null, access_token);

      originalRequest.headers.Authorization = `Bearer ${access_token}`;
      return apiClient(originalRequest);
    } catch (refreshError: any) {
      processQueue(refreshError, null);
      setAuthToken(null);
      await clearTokens();
      onAuthFailureCallback?.();
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  }
);
