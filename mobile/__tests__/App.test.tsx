import * as Notifications from 'expo-notifications';
import React from 'react';

jest.mock('expo-notifications', () => ({
  setNotificationHandler: jest.fn(),
  addNotificationResponseReceivedListener: jest.fn(() => ({ remove: jest.fn() })),
}));

jest.mock('react-native', () => ({
  View: 'View',
  Text: 'Text',
  TextInput: 'TextInput',
  TouchableOpacity: 'TouchableOpacity',
  StyleSheet: { create: jest.fn((styles) => styles) },
  ActivityIndicator: 'ActivityIndicator',
  Platform: { OS: 'android' },
  AppState: { addEventListener: jest.fn(() => ({ remove: jest.fn() })) },
  NativeModules: { SourceCode: { scriptURL: '' } }
}), { virtual: true });

jest.mock('@react-navigation/native', () => ({
  NavigationContainer: 'NavigationContainer',
  createNavigationContainerRef: jest.fn(() => ({
    isReady: jest.fn(),
    navigate: jest.fn(),
  })),
}));

jest.mock('@react-navigation/bottom-tabs', () => ({
  createBottomTabNavigator: jest.fn(() => ({ Navigator: 'Navigator', Screen: 'Screen' })),
}));

jest.mock('@react-navigation/native-stack', () => ({
  createNativeStackNavigator: jest.fn(() => ({ Navigator: 'Navigator', Screen: 'Screen' })),
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

describe('App', () => {
  it('registers the foreground notification handler on startup', async () => {
    // Importing App triggers the top-level side effects (setNotificationHandler)
    require('../App');

    expect(Notifications.setNotificationHandler).toHaveBeenCalledWith({
      handleNotification: expect.any(Function),
    });

    // Verify the function behavior
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
});
