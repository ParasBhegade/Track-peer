import { resolveApiUrl } from '../client';
import { Platform } from 'react-native';
import Constants from 'expo-constants';

jest.mock('expo-constants', () => ({
  expoConfig: {
    hostUri: undefined
  }
}));

jest.mock('react-native', () => ({
  Platform: {
    OS: 'android'
  }
}));

describe('resolveApiUrl', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.resetModules();
    process.env = { ...originalEnv };
    // @ts-ignore
    global.__DEV__ = true;
    Constants.expoConfig = {} as any;
    Platform.OS = 'android';
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('uses EXPO_PUBLIC_API_URL override if present', () => {
    process.env.EXPO_PUBLIC_API_URL = 'http://custom.api.com';
    expect(resolveApiUrl()).toBe('http://custom.api.com');
  });

  it('resolves physical-device development host from hostUri', () => {
    Constants.expoConfig = { hostUri: '192.168.42.252:8081' } as any;
    expect(resolveApiUrl()).toBe('http://192.168.42.252:8000');
  });

  it('falls back to emulator 10.0.2.2 if hostUri is localhost/127.0.0.1 (ADB reverse)', () => {
    Constants.expoConfig = { hostUri: '127.0.0.1:8081' } as any;
    expect(resolveApiUrl()).toBe('http://10.0.2.2:8000');

    Constants.expoConfig = { hostUri: 'localhost:8081' } as any;
    expect(resolveApiUrl()).toBe('http://10.0.2.2:8000');
  });

  it('falls back to emulator 10.0.2.2 if hostUri is missing', () => {
    Constants.expoConfig = undefined as any;
    expect(resolveApiUrl()).toBe('http://10.0.2.2:8000');
  });

  it('resolves localhost for iOS simulator if hostUri missing', () => {
    Constants.expoConfig = undefined as any;
    Platform.OS = 'ios';
    expect(resolveApiUrl()).toBe('http://localhost:8000');
  });
  
  it('falls back to base defaults in production (__DEV__ is false)', () => {
    // @ts-ignore
    global.__DEV__ = false;
    Constants.expoConfig = { hostUri: '192.168.42.252:8081' } as any;
    expect(resolveApiUrl()).toBe('http://10.0.2.2:8000'); // Assuming Android
  });
});
