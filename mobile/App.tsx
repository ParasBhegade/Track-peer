import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  ScrollView,
  SafeAreaView,
  AppState,
} from 'react-native';
import { useFonts, SpaceGrotesk_700Bold, SpaceGrotesk_600SemiBold } from '@expo-google-fonts/space-grotesk';
import { Inter_400Regular } from '@expo-google-fonts/inter';
import { login, register, logout as logoutApi, restoreSession } from './src/api/auth';
import { setOnAuthFailure } from './src/api/client';
import { colors, typography, spacing } from './src/theme';
import { TodayScreen } from './src/features/TodayScreen';
import { CalendarScreen } from './src/features/CalendarScreen';
import { StatsScreen } from './src/features/StatsScreen';
import { HabitDetailsScreen } from './src/features/HabitDetailsScreen';
import { NavigationContainer, createNavigationContainerRef } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { MaterialIcons } from '@expo/vector-icons';
import * as Notifications from 'expo-notifications';
import { reconcile, clearAllHabitNotifications } from './src/notifications/reconcile';

import { AuthContext } from './src/AuthContext';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

export const navigationRef = createNavigationContainerRef();

const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator();

function HomeStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="TodayMain" component={TodayScreen} />
      <Stack.Screen name="HabitDetails" component={HabitDetailsScreen} />
    </Stack.Navigator>
  );
}

function AuthenticatedApp() {
  return (
    <NavigationContainer ref={navigationRef}>
      <Tab.Navigator
        screenOptions={{
          headerShown: false,
          tabBarActiveTintColor: colors.primary,
          tabBarInactiveTintColor: colors['on-surface-variant'],
          tabBarStyle: {
            backgroundColor: colors.surface,
            borderTopColor: colors.outline,
          },
        }}
      >
        <Tab.Screen 
          name="Today" 
          component={HomeStack} 
          options={{ tabBarIcon: ({ color }) => <MaterialIcons name="check-circle" size={24} color={color} /> }} 
        />
        <Tab.Screen 
          name="Calendar" 
          component={CalendarScreen} 
          options={{ tabBarIcon: ({ color }) => <MaterialIcons name="calendar-today" size={24} color={color} /> }} 
        />
        <Tab.Screen 
          name="Stats" 
          component={StatsScreen} 
          options={{ tabBarIcon: ({ color }) => <MaterialIcons name="bar-chart" size={24} color={color} /> }} 
        />
      </Tab.Navigator>
    </NavigationContainer>
  );
}

const getDefaultTimezone = (): string => {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (tz && typeof tz === 'string') return tz;
  } catch {}
  return 'UTC';
};

export default function App() {
  const [fontsLoaded] = useFonts({
    SpaceGrotesk_700Bold,
    SpaceGrotesk_600SemiBold,
    Inter_400Regular,
  });

  const [isRestoringSession, setIsRestoringSession] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [timezone, setTimezone] = useState(getDefaultTimezone);
  const [showPassword, setShowPassword] = useState(false);
  const [authError, setAuthError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let isMounted = true;

    setOnAuthFailure(() => {
      if (isMounted) {
        setAuthenticated(false);
      }
    });

    const initAuth = async () => {
      try {
        const isValid = await restoreSession();
        if (isMounted) {
          setAuthenticated(isValid);
        }
      } catch {
        if (isMounted) {
          setAuthenticated(false);
        }
      } finally {
        if (isMounted) {
          setIsRestoringSession(false);
        }
      }
    };

    initAuth();

    return () => {
      isMounted = false;
      setOnAuthFailure(null);
    };
  }, []);

  useEffect(() => {
    const responseListener = Notifications.addNotificationResponseReceivedListener(response => {
      const data = response.notification.request.content.data;
      if (data?.screen === 'today') {
        if (navigationRef.isReady()) {
          navigationRef.navigate('Today' as never);
        }
      }
    });

    return () => {
      responseListener.remove();
    };
  }, []);

  useEffect(() => {
    if (!authenticated) return;
    
    reconcile();

    const subscription = AppState.addEventListener('change', nextAppState => {
      if (nextAppState === 'active') {
        reconcile();
      }
    });

    return () => {
      subscription.remove();
    };
  }, [authenticated]);

  if (!fontsLoaded || isRestoringSession) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  const handleLogout = async () => {
    try {
      await clearAllHabitNotifications();
    } catch {}
    try {
      await logoutApi();
    } catch {}
    setAuthenticated(false);
  };

  const handleLogin = async () => {
    try {
      setAuthError('');
      if (!email.trim() || !password.trim()) {
        setAuthError('Email and password are required');
        return;
      }
      setIsSubmitting(true);
      await login(email.trim(), password);
      setAuthenticated(true);
    } catch (err: any) {
      const msg = err?.response?.data?.error?.message || err?.response?.data?.detail || err?.message || 'Login failed';
      setAuthError(typeof msg === 'string' ? msg : 'Login failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRegister = async () => {
    try {
      setAuthError('');
      if (!displayName.trim()) {
        setAuthError('Display name is required');
        return;
      }
      if (!email.trim()) {
        setAuthError('Email is required');
        return;
      }
      if (password.length < 8) {
        setAuthError('Password must be at least 8 characters');
        return;
      }
      if (!timezone.trim()) {
        setAuthError('Timezone is required');
        return;
      }

      setIsSubmitting(true);
      await register(email.trim(), password, displayName.trim(), timezone.trim());
      setAuthenticated(true);
    } catch (err: any) {
      let msg = 'Registration failed';
      if (err?.response?.data?.error?.message) {
        msg = err.response.data.error.message;
      } else if (err?.response?.data?.error?.code === 'email_taken') {
        msg = 'This email address is already registered';
      } else if (Array.isArray(err?.response?.data?.detail)) {
        msg = err.response.data.detail[0]?.msg || 'Validation error';
      } else if (typeof err?.response?.data?.detail === 'string') {
        msg = err.response.data.detail;
      } else if (err?.message) {
        msg = err.message;
      }
      setAuthError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const toggleAuthMode = () => {
    setAuthMode(current => (current === 'login' ? 'register' : 'login'));
    setAuthError('');
  };

  if (!authenticated) {
    const isRegister = authMode === 'register';

    return (
      <SafeAreaView style={styles.safeArea}>
        <ScrollView contentContainerStyle={styles.authContainer} keyboardShouldPersistTaps="handled">
          <Text style={styles.authTitle}>HABIT TRACKER</Text>
          <Text style={styles.authSubtitle}>
            {isRegister ? 'NEW OPERATOR REGISTRATION' : 'AUTHENTICATION REQUIRED'}
          </Text>

          {isRegister && (
            <TextInput
              style={styles.input}
              placeholder="DISPLAY NAME"
              placeholderTextColor={colors['on-surface-variant']}
              value={displayName}
              onChangeText={setDisplayName}
              autoCapitalize="words"
            />
          )}

          <TextInput
            style={styles.input}
            placeholder="EMAIL"
            placeholderTextColor={colors['on-surface-variant']}
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            keyboardType="email-address"
          />

          <View style={styles.passwordContainer}>
            <TextInput
              style={[styles.input, styles.passwordInput]}
              placeholder={isRegister ? 'PASSWORD (MIN 8 CHARS)' : 'PASSWORD'}
              placeholderTextColor={colors['on-surface-variant']}
              value={password}
              onChangeText={setPassword}
              secureTextEntry={!showPassword}
            />
            <TouchableOpacity
              style={styles.eyeIcon}
              onPress={() => setShowPassword(!showPassword)}
            >
              <MaterialIcons
                name={showPassword ? 'visibility-off' : 'visibility'}
                size={24}
                color={colors.primary}
              />
            </TouchableOpacity>
          </View>

          {isRegister && (
            <TextInput
              style={styles.input}
              placeholder="TIMEZONE"
              placeholderTextColor={colors['on-surface-variant']}
              value={timezone}
              onChangeText={setTimezone}
              autoCapitalize="none"
            />
          )}

          {authError ? <Text style={styles.errorText}>{authError}</Text> : null}

          <TouchableOpacity
            style={styles.loginBtn}
            onPress={isRegister ? handleRegister : handleLogin}
            disabled={isSubmitting}
          >
            <Text style={styles.loginBtnText}>
              {isSubmitting ? '...' : (isRegister ? 'REGISTER' : 'LOGIN')}
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.switchBtn}
            onPress={toggleAuthMode}
            disabled={isSubmitting}
          >
            <Text style={styles.switchBtnText}>
              {isRegister ? 'ALREADY REGISTERED? LOGIN' : 'NEED AN ACCOUNT? REGISTER'}
            </Text>
          </TouchableOpacity>
        </ScrollView>
      </SafeAreaView>
    );
  }

  return (
    <AuthContext.Provider value={{ logout: handleLogout }}>
      <AuthenticatedApp />
    </AuthContext.Provider>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.surface,
  },
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.surface,
  },
  authContainer: {
    flexGrow: 1,
    backgroundColor: colors.surface,
    padding: spacing.xl,
    justifyContent: 'center',
  },
  authTitle: {
    ...typography.displayMobile,
    color: colors.primary,
    marginBottom: spacing.xs,
  },
  authSubtitle: {
    ...typography.labelLg,
    color: colors['on-surface-variant'],
    marginBottom: spacing.xl,
  },
  input: {
    borderBottomWidth: 3,
    borderBottomColor: colors.primary,
    marginBottom: spacing.lg,
    paddingVertical: spacing.sm,
    ...typography.headlineMd,
    color: colors.primary,
  },
  passwordContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    borderBottomWidth: 3,
    borderBottomColor: colors.primary,
    marginBottom: spacing.lg,
  },
  passwordInput: {
    flex: 1,
    borderBottomWidth: 0,
    marginBottom: 0,
  },
  eyeIcon: {
    padding: spacing.xs,
  },
  loginBtn: {
    backgroundColor: colors['secondary-container'],
    borderWidth: 2.5,
    borderColor: colors.primary,
    paddingVertical: 16,
    alignItems: 'center',
    marginTop: spacing.md,
    shadowColor: colors.primary,
    shadowOffset: { width: 4, height: 4 },
    shadowOpacity: 1,
    shadowRadius: 0,
  },
  loginBtnText: {
    ...typography.labelLg,
    color: colors.primary,
  },
  switchBtn: {
    backgroundColor: colors['surface-container-high'],
    borderWidth: 2,
    borderColor: colors.primary,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: spacing.md,
  },
  switchBtnText: {
    ...typography.labelMd,
    color: colors.primary,
  },
  errorText: {
    ...typography.labelMd,
    color: colors.error,
    marginBottom: spacing.sm,
  },
});
