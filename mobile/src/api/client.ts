import axios from 'axios';
import { Platform } from 'react-native';
import Constants from 'expo-constants';

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

export const setAuthToken = (token: string | null) => {
  currentToken = token;
  if (token) {
    apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  } else {
    delete apiClient.defaults.headers.common['Authorization'];
  }
};

export const getAuthToken = () => currentToken;
