import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

/**
 * Android Notification Channel setup.
 * Must be called early in the app lifecycle (or before scheduling)
 * to ensure notifications can be delivered.
 */
export async function configureAndroidChannel(): Promise<void> {
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'Habit Reminders',
      description: 'Reminders for your scheduled habits',
      importance: Notifications.AndroidImportance.MAX,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: '#FF231F7C',
    });
  }
}

/**
 * Gets the current notification permission status.
 */
export async function getPermissionStatus(): Promise<Notifications.NotificationPermissionsStatus> {
  return await Notifications.getPermissionsAsync();
}

/**
 * Requests notification permission from the user.
 */
export async function requestPermission(): Promise<Notifications.NotificationPermissionsStatus> {
  return await Notifications.requestPermissionsAsync({
    ios: {
      allowAlert: true,
      allowBadge: true,
      allowSound: true,
    },
  });
}
