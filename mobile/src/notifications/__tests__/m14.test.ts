import * as Notifications from 'expo-notifications';
import { reconcile } from '../reconcile';
import * as permissions from '../permissions';
import * as remindersApi from '../../api/reminders';
import { ReminderPlanResponse } from '../../api/reminders';
import { planToTriggers } from '../planToTriggers';

jest.mock('expo-notifications', () => ({
  getAllScheduledNotificationsAsync: jest.fn(),
  cancelScheduledNotificationAsync: jest.fn(),
  scheduleNotificationAsync: jest.fn(),
  SchedulableTriggerInputTypes: { DATE: 'date' },
}));

jest.mock('../permissions', () => ({
  getPermissionStatus: jest.fn(),
  configureAndroidChannel: jest.fn(),
}));

jest.mock('../../api/reminders', () => ({
  fetchReminderPlan: jest.fn(),
}));

describe('M14 Integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('1. Successful reminder-plan fetch flows into planToTriggers and 2. Resulting triggers flow into reconcile (Expo scheduling)', async () => {
    (permissions.getPermissionStatus as jest.Mock).mockResolvedValue({ granted: true });
    
    const now = new Date();
    const tomorrow = new Date(now);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowIso = tomorrow.toISOString().split('T')[0];

    const plan: ReminderPlanResponse = {
      timezone: 'UTC',
      from: tomorrowIso,
      to: tomorrowIso,
      reminders: [
        {
          notification_id: `habit:14:${tomorrowIso}`,
          habit_id: '14',
          habit_name: 'M14 Habit',
          occurrence_date: tomorrowIso,
          reminder_time: '12:00:00',
        }
      ]
    };
    
    (remindersApi.fetchReminderPlan as jest.Mock).mockResolvedValue(plan);
    (Notifications.getAllScheduledNotificationsAsync as jest.Mock).mockResolvedValue([]);

    await reconcile();

    // 3. Correct ReminderPlan is passed through unchanged (implied by correct ID generation)
    // 7. Existing M13 deterministic IDs remain intact
    expect(Notifications.scheduleNotificationAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        identifier: `habit:14:${tomorrowIso}`,
        content: {
          title: 'M14 Habit',
          body: 'Time for your habit.',
          data: {
            habit_id: '14',
            occurrence_date: tomorrowIso,
            screen: 'today',
          }
        }
      })
    );
  });

  it('4. API failure is handled gracefully', async () => {
    (permissions.getPermissionStatus as jest.Mock).mockResolvedValue({ granted: true });
    (remindersApi.fetchReminderPlan as jest.Mock).mockRejectedValue(new Error('Network error'));
    
    // Should not throw and crash the application
    await expect(reconcile()).resolves.not.toThrow();
    
    expect(remindersApi.fetchReminderPlan).toHaveBeenCalled();
    // Flow stops gracefully before checking Expo
    expect(Notifications.getAllScheduledNotificationsAsync).not.toHaveBeenCalled();
  });

  it('5. Permission denial remains graceful', async () => {
    (permissions.getPermissionStatus as jest.Mock).mockResolvedValue({ granted: false });
    
    await expect(reconcile()).resolves.not.toThrow();
    
    // Flow stops gracefully before fetching plan
    expect(remindersApi.fetchReminderPlan).not.toHaveBeenCalled();
    expect(Notifications.getAllScheduledNotificationsAsync).not.toHaveBeenCalled();
  });

  it('6. Empty reminder plan results in reconciliation with zero desired triggers', async () => {
    (permissions.getPermissionStatus as jest.Mock).mockResolvedValue({ granted: true });
    (remindersApi.fetchReminderPlan as jest.Mock).mockResolvedValue({
      timezone: 'UTC',
      from: '2026-10-01',
      to: '2026-10-14',
      reminders: []
    });
    
    (Notifications.getAllScheduledNotificationsAsync as jest.Mock).mockResolvedValue([
      { identifier: 'habit:old:2026-10-01' }
    ]);

    await reconcile();

    expect(remindersApi.fetchReminderPlan).toHaveBeenCalled();
    // Since plan is empty, desired triggers are 0, so any existing habit triggers must be cancelled.
    expect(Notifications.cancelScheduledNotificationAsync).toHaveBeenCalledWith('habit:old:2026-10-01');
    expect(Notifications.scheduleNotificationAsync).not.toHaveBeenCalled();
  });

  it('9. Repeated integration calls remain safe/idempotent', async () => {
    (permissions.getPermissionStatus as jest.Mock).mockResolvedValue({ granted: true });
    
    const now = new Date();
    const tomorrow = new Date(now);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowIso = tomorrow.toISOString().split('T')[0];

    const plan: ReminderPlanResponse = {
      timezone: 'UTC',
      from: tomorrowIso,
      to: tomorrowIso,
      reminders: [
        {
          notification_id: `habit:idempotent:${tomorrowIso}`,
          habit_id: 'idempotent',
          habit_name: 'Idempotent Habit',
          occurrence_date: tomorrowIso,
          reminder_time: '12:00:00',
        }
      ]
    };
    
    (remindersApi.fetchReminderPlan as jest.Mock).mockResolvedValue(plan);
    
    // First call: no existing
    (Notifications.getAllScheduledNotificationsAsync as jest.Mock).mockResolvedValue([]);
    await reconcile();
    expect(Notifications.scheduleNotificationAsync).toHaveBeenCalledTimes(1);

    // Second call: existing matches desired
    jest.clearAllMocks();
    (Notifications.getAllScheduledNotificationsAsync as jest.Mock).mockResolvedValue([
      { identifier: `habit:idempotent:${tomorrowIso}` }
    ]);
    await reconcile();
    expect(Notifications.scheduleNotificationAsync).not.toHaveBeenCalled();
    expect(Notifications.cancelScheduledNotificationAsync).not.toHaveBeenCalled();
  });
});
