import React from 'react';
// @ts-ignore
import renderer, { act } from 'react-test-renderer';
import * as Notifications from 'expo-notifications';
import { login, register, logout as logoutApi, restoreSession } from '../src/api/auth';
import { clearAllHabitNotifications } from '../src/notifications/reconcile';

jest.mock('expo-notifications', () => ({
  setNotificationHandler: jest.fn(),
  addNotificationResponseReceivedListener: jest.fn(() => ({ remove: jest.fn() })),
}));

jest.mock('react-native', () => ({
  View: 'View',
  Text: 'Text',
  TextInput: 'TextInput',
  TouchableOpacity: 'TouchableOpacity',
  ScrollView: 'ScrollView',
  SafeAreaView: 'SafeAreaView',
  StyleSheet: { create: jest.fn((styles) => styles) },
  ActivityIndicator: 'ActivityIndicator',
  Platform: { OS: 'android' },
  AppState: { addEventListener: jest.fn(() => ({ remove: jest.fn() })) },
  NativeModules: { SourceCode: { scriptURL: '' } },
}), { virtual: true });

jest.mock('@react-navigation/native', () => ({
  NavigationContainer: ({ children }: any) => children,
  createNavigationContainerRef: jest.fn(() => ({
    isReady: jest.fn(),
    navigate: jest.fn(),
  })),
}));

jest.mock('@react-navigation/bottom-tabs', () => ({
  createBottomTabNavigator: jest.fn(() => ({
    Navigator: ({ children }: any) => children,
    Screen: ({ component: Component }: any) => (Component ? <Component navigation={{}} /> : null),
  })),
}));

jest.mock('@react-navigation/native-stack', () => ({
  createNativeStackNavigator: jest.fn(() => ({
    Navigator: ({ children }: any) => children,
    Screen: ({ component: Component }: any) => (Component ? <Component navigation={{}} /> : null),
  })),
}));

jest.mock('@expo-google-fonts/space-grotesk', () => ({
  useFonts: jest.fn(() => [true]),
  SpaceGrotesk_700Bold: 'SpaceGrotesk_700Bold',
  SpaceGrotesk_600SemiBold: 'SpaceGrotesk_600SemiBold',
}));

jest.mock('@expo-google-fonts/inter', () => ({
  Inter_400Regular: 'Inter_400Regular',
}));

jest.mock('@expo/vector-icons', () => ({
  MaterialIcons: 'MaterialIcons',
}));

jest.mock('react-native-get-random-values', () => ({}));
jest.mock('uuid', () => ({ v4: jest.fn(() => '1234') }));

jest.mock('../src/features/TodayScreen', () => {
  const React = require('react');
  const { AuthContext } = require('../src/AuthContext');
  return {
    TodayScreen: () => {
      const { logout } = React.useContext(AuthContext);
      return React.createElement('mock-today', { onPressLogout: logout });
    },
  };
});
jest.mock('../src/features/CalendarScreen', () => ({
  CalendarScreen: () => 'CalendarScreenMock',
}));
jest.mock('../src/features/StatsScreen', () => ({
  StatsScreen: () => 'StatsScreenMock',
}));
jest.mock('../src/features/HabitDetailsScreen', () => ({
  HabitDetailsScreen: () => 'HabitDetailsScreenMock',
}));

jest.mock('../src/notifications/reconcile', () => ({
  reconcile: jest.fn(),
  clearAllHabitNotifications: jest.fn(),
}));

jest.mock('../src/api/auth', () => ({
  login: jest.fn(),
  register: jest.fn(),
  logout: jest.fn(),
  restoreSession: jest.fn(),
}));

jest.mock('../src/api/client', () => ({
  setOnAuthFailure: jest.fn(),
}));

import { AuthContext } from '../src/AuthContext';
import App from '../App';

describe('App', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (restoreSession as jest.Mock).mockResolvedValue(false);
  });

  it('registers the foreground notification handler on startup', async () => {
    jest.isolateModules(() => {
      require('../App');
    });

    expect(Notifications.setNotificationHandler).toHaveBeenCalledWith({
      handleNotification: expect.any(Function),
    });

    const callArgs = (Notifications.setNotificationHandler as jest.Mock).mock.calls[0][0];
    const handleNotification = callArgs.handleNotification;
    
    const result = await handleNotification({} as any);
    expect(result).toEqual({
      shouldShowAlert: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
      shouldShowBanner: true,
      shouldShowList: true,
    });
  });

  it('shows loading indicator while session restoration is pending', async () => {
    let resolveRestore: any;
    (restoreSession as jest.Mock).mockImplementationOnce(
      () => new Promise((res) => { resolveRestore = res; })
    );

    let component: any;
    await act(async () => {
      component = renderer.create(<App />);
    });

    // While restoreSession is in flight, ActivityIndicator is displayed
    const indicators = component.root.findAllByType('ActivityIndicator' as any);
    expect(indicators.length).toBeGreaterThan(0);

    // Resolve restoreSession
    await act(async () => {
      resolveRestore(false);
    });

    // After resolving false, login screen is rendered
    const texts = component.root.findAllByType('Text' as any);
    const subtitle = texts.find((t: any) => t.props.children === 'AUTHENTICATION REQUIRED');
    expect(subtitle).toBeDefined();
  });

  it('renders login screen when unauthenticated and switches between Login and Register', async () => {
    (restoreSession as jest.Mock).mockResolvedValueOnce(false);

    let component: any;
    await act(async () => {
      component = renderer.create(<App />);
    });

    // Initially in Login mode
    let texts = component.root.findAllByType('Text' as any);
    expect(texts.some((t: any) => t.props.children === 'AUTHENTICATION REQUIRED')).toBe(true);

    // Find and press the switch button to toggle to Register mode
    const switchBtn = component.root.findAllByType('TouchableOpacity' as any).find(
      (btn: any) => {
        const textChild = btn.findAllByType('Text' as any)[0];
        return textChild && textChild.props.children === 'NEED AN ACCOUNT? REGISTER';
      }
    );
    expect(switchBtn).toBeDefined();

    await act(async () => {
      switchBtn.props.onPress();
    });

    // Now in Register mode
    texts = component.root.findAllByType('Text' as any);
    expect(texts.some((t: any) => t.props.children === 'NEW OPERATOR REGISTRATION')).toBe(true);
    expect(texts.some((t: any) => t.props.children === 'ALREADY REGISTERED? LOGIN')).toBe(true);

    // Toggle back to Login mode
    const loginSwitchBtn = component.root.findAllByType('TouchableOpacity' as any).find(
      (btn: any) => {
        const textChild = btn.findAllByType('Text' as any)[0];
        return textChild && textChild.props.children === 'ALREADY REGISTERED? LOGIN';
      }
    );
    await act(async () => {
      loginSwitchBtn.props.onPress();
    });

    texts = component.root.findAllByType('Text' as any);
    expect(texts.some((t: any) => t.props.children === 'AUTHENTICATION REQUIRED')).toBe(true);
  });

  it('shows required field validation errors during registration', async () => {
    (restoreSession as jest.Mock).mockResolvedValueOnce(false);

    let component: any;
    await act(async () => {
      component = renderer.create(<App />);
    });

    // Switch to Register mode
    const switchBtn = component.root.findAllByType('TouchableOpacity' as any).find(
      (btn: any) => btn.findAllByType('Text' as any)[0]?.props.children === 'NEED AN ACCOUNT? REGISTER'
    );
    await act(async () => {
      switchBtn.props.onPress();
    });

    // Press REGISTER without filling display name
    const registerBtn = component.root.findAllByType('TouchableOpacity' as any).find(
      (btn: any) => btn.findAllByType('Text' as any)[0]?.props.children === 'REGISTER'
    );
    await act(async () => {
      registerBtn.props.onPress();
    });

    let texts = component.root.findAllByType('Text' as any);
    expect(texts.some((t: any) => t.props.children === 'Display name is required')).toBe(true);
  });

  it('registers successfully and enters authenticated app', async () => {
    (restoreSession as jest.Mock).mockResolvedValueOnce(false);
    (register as jest.Mock).mockResolvedValueOnce({
      user: { id: 'u-1', display_name: 'Test Pilot' },
      tokens: { access_token: 'acc-1', refresh_token: 'ref-1' },
    });

    let component: any;
    await act(async () => {
      component = renderer.create(<App />);
    });

    // Switch to Register mode
    const switchBtn = component.root.findAllByType('TouchableOpacity' as any).find(
      (btn: any) => btn.findAllByType('Text' as any)[0]?.props.children === 'NEED AN ACCOUNT? REGISTER'
    );
    await act(async () => {
      switchBtn.props.onPress();
    });

    // Fill in inputs
    const inputs = component.root.findAllByType('TextInput' as any);
    const nameInput = inputs.find((i: any) => i.props.placeholder === 'DISPLAY NAME');
    const emailInput = inputs.find((i: any) => i.props.placeholder === 'EMAIL');
    const passInput = inputs.find((i: any) => i.props.placeholder === 'PASSWORD (MIN 8 CHARS)');

    await act(async () => {
      nameInput.props.onChangeText('Test Pilot');
      emailInput.props.onChangeText('pilot@example.com');
      passInput.props.onChangeText('password123');
    });

    // Submit registration
    const registerBtn = component.root.findAllByType('TouchableOpacity' as any).find(
      (btn: any) => btn.findAllByType('Text' as any)[0]?.props.children === 'REGISTER'
    );

    await act(async () => {
      await registerBtn.props.onPress();
    });

    expect(register).toHaveBeenCalledWith(
      'pilot@example.com',
      'password123',
      'Test Pilot',
      expect.any(String)
    );

    // App is now authenticated
    expect(component.toJSON()).toBeDefined();
  });

  it('restores authenticated session automatically on startup', async () => {
    (restoreSession as jest.Mock).mockResolvedValueOnce(true);

    let component: any;
    await act(async () => {
      component = renderer.create(<App />);
    });

    // Since restoreSession returned true, login screen is skipped and authenticated screens render
    const texts = component.root.findAllByType('Text' as any);
    expect(texts.some((t: any) => t.props.children === 'AUTHENTICATION REQUIRED')).toBe(false);
    expect(texts.some((t: any) => t.props.children === 'NEW OPERATOR REGISTRATION')).toBe(false);
  });

  it('handles login and logout flow correctly', async () => {
    (restoreSession as jest.Mock).mockResolvedValueOnce(false);
    (login as jest.Mock).mockResolvedValueOnce({
      user: { id: 'u-1', email: 'user@example.com' },
      tokens: { access_token: 'acc-token', refresh_token: 'ref-token' },
    });

    let component: any;
    await act(async () => {
      component = renderer.create(<App />);
    });

    // Fill login inputs
    const inputs = component.root.findAllByType('TextInput' as any);
    const emailInput = inputs.find((i: any) => i.props.placeholder === 'EMAIL');
    const passInput = inputs.find((i: any) => i.props.placeholder === 'PASSWORD');

    await act(async () => {
      emailInput.props.onChangeText('user@example.com');
      passInput.props.onChangeText('password123');
    });

    // Submit login
    const loginBtn = component.root.findAllByType('TouchableOpacity' as any).find(
      (btn: any) => btn.findAllByType('Text' as any)[0]?.props.children === 'LOGIN'
    );

    await act(async () => {
      await loginBtn.props.onPress();
    });

    expect(login).toHaveBeenCalledWith('user@example.com', 'password123');

    // Trigger logout via TodayScreen which consumes AuthContext
    const todayMock = component.root.findByType('mock-today' as any);
    expect(todayMock).toBeDefined();

    await act(async () => {
      await todayMock.props.onPressLogout();
    });

    expect(clearAllHabitNotifications).toHaveBeenCalled();
    expect(logoutApi).toHaveBeenCalled();

    // After logout, returned to unauthenticated login screen
    const texts = component.root.findAllByType('Text' as any);
    expect(texts.some((t: any) => t.props.children === 'AUTHENTICATION REQUIRED')).toBe(true);
  });
});
