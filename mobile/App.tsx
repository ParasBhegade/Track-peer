import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { useFonts, SpaceGrotesk_700Bold, SpaceGrotesk_600SemiBold } from '@expo-google-fonts/space-grotesk';
import { Inter_400Regular } from '@expo-google-fonts/inter';
import { login } from './src/api/auth';
import { colors, typography, spacing } from './src/theme';
import { TodayScreen } from './src/features/TodayScreen';
import { CalendarScreen } from './src/features/CalendarScreen';
import { StatsScreen } from './src/features/StatsScreen';
import { HabitDetailsScreen } from './src/features/HabitDetailsScreen';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { MaterialIcons } from '@expo/vector-icons';

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
    <NavigationContainer>
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

export default function App() {
  const [fontsLoaded] = useFonts({
    SpaceGrotesk_700Bold,
    SpaceGrotesk_600SemiBold,
    Inter_400Regular,
  });

  const [authenticated, setAuthenticated] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [authError, setAuthError] = useState('');
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  if (!fontsLoaded) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#000" />
      </View>
    );
  }

  const handleLogin = async () => {
    try {
      setAuthError('');
      setIsLoggingIn(true);
      await login(email, password);
      setAuthenticated(true);
    } catch (err: any) {
      setAuthError(err?.message || 'Login failed');
    } finally {
      setIsLoggingIn(false);
    }
  };

  if (!authenticated) {
    return (
      <View style={styles.authContainer}>
        <Text style={styles.authTitle}>HABIT TRACKER</Text>
        <Text style={styles.authSubtitle}>AUTHENTICATION REQUIRED</Text>

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
            placeholder="PASSWORD"
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
              name={showPassword ? "visibility-off" : "visibility"} 
              size={24} 
              color={colors.primary} 
            />
          </TouchableOpacity>
        </View>

        {authError ? <Text style={styles.errorText}>{authError}</Text> : null}

        <TouchableOpacity 
          style={styles.loginBtn} 
          onPress={handleLogin}
          disabled={isLoggingIn}
        >
          <Text style={styles.loginBtnText}>{isLoggingIn ? '...' : 'LOGIN'}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return <AuthenticatedApp />;
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.surface,
  },
  authContainer: {
    flex: 1,
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
  errorText: {
    ...typography.labelMd,
    color: colors.error,
    marginBottom: spacing.sm,
  },
});
