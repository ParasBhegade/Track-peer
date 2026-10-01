import * as Notifications from 'expo-notifications';
import { planToTriggers } from '../planToTriggers';
import { reconcile, clearAllHabitNotifications } from '../reconcile';
import * as permissions from '../permissions';
import * as remindersApi from '../../api/reminders';
import { ReminderPlanResponse } from '../../api/reminders';

// Mock dependencies
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

describe('planToTriggers', () => {
  it('drops reminders in the past', () => {
    const now = new Date('2026-09-28T12:00:00');
    const plan: ReminderPlanResponse = {
      timezone: 'UTC',
      from: '2026-09-28',
      to: '2026-10-11',
      reminders: [
        {
          notification_id: 'habit:1:2026-09-28',
          habit_id: '1',
          habit_name: 'Past Habit',
          occurrence_date: '2026-09-28',
          reminder_time: '10:00:00', // Past
        },
        {
          notification_id: 'habit:2:2026-09-28',
          habit_id: '2',
          habit_name: 'Future Habit',
          occurrence_date: '2026-09-28',
          reminder_time: '14:00:00', // Future
        }
      ]
    };

    const triggers = planToTriggers(plan, now);
    expect(triggers).toHaveLength(1);
    expect(triggers[0].id).toBe('habit:2:2026-09-28');
  });

  it('sorts soonest first and truncates globally to 60', () => {
    const now = new Date('2026-09-28T12:00:00');
    const reminders = [];
    
    // Create 100 reminders starting from tomorrow
    const baseDate = new Date('2026-10-01T10:00:00Z');
    for (let i = 0; i < 100; i++) {
      const d = new Date(baseDate);
      d.setDate(d.getDate() + i);
      const dateStr = d.toISOString().split('T')[0];
      reminders.push({
        notification_id: `habit:1:${dateStr}`,
        habit_id: '1',
        habit_name: `Habit ${i}`,
        occurrence_date: dateStr,
        reminder_time: '10:00:00',
      });
    }

    // Shuffle the array to ensure sorting works
    const shuffled = [...reminders].sort(() => 0.5 - Math.random());

    const plan: ReminderPlanResponse = {
      timezone: 'UTC',
      from: '2026-10-01',
      to: '2027-01-08',
      reminders: shuffled,
    };

    const triggers = planToTriggers(plan, now);
    expect(triggers).toHaveLength(60);
    
    // Earliest should be kept (index 0 should be 2026-10-01)
    expect(triggers[0].id).toBe('habit:1:2026-10-01');
    expect(triggers[59].id).toBe('habit:1:2026-11-29');
  });

  it('constructs deterministic IDs and correct payloads', () => {
    const now = new Date('2026-09-28T12:00:00');
    const plan: ReminderPlanResponse = {
      timezone: 'UTC',
      from: '2026-09-28',
      to: '2026-10-11',
      reminders: [
        {
          notification_id: 'habit:123:2026-09-29',
          habit_id: '123',
          habit_name: 'Test Name',
          occurrence_date: '2026-09-29',
          reminder_time: '10:00:00',
        }
      ]
    };

    const triggers = planToTriggers(plan, now);
    expect(triggers[0]).toEqual({
      id: 'habit:123:2026-09-29',
      fireAt: expect.any(Date),
      title: 'Test Name',
      body: 'Time for your habit.',
      data: {
        habit_id: '123',
        occurrence_date: '2026-09-29',
        screen: 'today',
      }
    });
    // Check Date correctness
    expect(triggers[0].fireAt.getHours()).toBe(10);
    expect(triggers[0].fireAt.getMinutes()).toBe(0);
  });

  it('respects DST boundaries correctly', () => {
    const now = new Date('2026-03-01T12:00:00Z');
    
    // In US/Eastern, 2026 Spring Forward is March 8, 2026
    // March 7 is EST (UTC-5)
    // March 9 is EDT (UTC-4)
    
    const plan: ReminderPlanResponse = {
      timezone: 'America/New_York',
      from: '2026-03-07',
      to: '2026-03-09',
      reminders: [
        {
          notification_id: 'habit:1:2026-03-07',
          habit_id: '1',
          habit_name: 'Pre DST',
          occurrence_date: '2026-03-07',
          reminder_time: '10:00:00',
        },
        {
          notification_id: 'habit:1:2026-03-09',
          habit_id: '1',
          habit_name: 'Post DST',
          occurrence_date: '2026-03-09',
          reminder_time: '10:00:00',
        }
      ]
    };

    const triggers = planToTriggers(plan, now);
    
    expect(triggers).toHaveLength(2);
    
    // Absolute UTC times should reflect the offset change
    // March 7 10:00 EST = 15:00 UTC
    // March 9 10:00 EDT = 14:00 UTC
    expect(triggers[0].fireAt.toISOString()).toBe('2026-03-07T15:00:00.000Z');
    expect(triggers[1].fireAt.toISOString()).toBe('2026-03-09T14:00:00.000Z');
  });
});

describe('reconcile', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('makes zero scheduler calls if no permission', async () => {
    (permissions.getPermissionStatus as jest.Mock).mockResolvedValue({ granted: false });
    
    await reconcile();
    
    expect(remindersApi.fetchReminderPlan).not.toHaveBeenCalled();
    expect(Notifications.scheduleNotificationAsync).not.toHaveBeenCalled();
  });

  it('cancels missing triggers and schedules new triggers', async () => {
    (permissions.getPermissionStatus as jest.Mock).mockResolvedValue({ granted: true });
    
    const now = new Date();
    // Simulate tomorrow at 10 AM
    const tomorrow = new Date(now);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowIso = tomorrow.toISOString().split('T')[0];

    const plan: ReminderPlanResponse = {
      timezone: 'UTC',
      from: tomorrowIso,
      to: tomorrowIso,
      reminders: [
        {
          notification_id: `habit:new:${tomorrowIso}`,
          habit_id: 'new',
          habit_name: 'New Habit',
          occurrence_date: tomorrowIso,
          reminder_time: '10:00:00',
        }
      ]
    };
    (remindersApi.fetchReminderPlan as jest.Mock).mockResolvedValue(plan);
    
    (Notifications.getAllScheduledNotificationsAsync as jest.Mock).mockResolvedValue([
      { identifier: `habit:old:${tomorrowIso}` }, // Should be cancelled
      { identifier: 'unrelated:123' }, // Should be ignored
    ]);

    await reconcile();

    // Cancel old habit notification
    expect(Notifications.cancelScheduledNotificationAsync).toHaveBeenCalledWith(`habit:old:${tomorrowIso}`);
    // Ignore unrelated notification
    expect(Notifications.cancelScheduledNotificationAsync).not.toHaveBeenCalledWith('unrelated:123');
    
    // Schedule new habit notification
    expect(Notifications.scheduleNotificationAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        identifier: `habit:new:${tomorrowIso}`
      })
    );
  });

  it('makes zero scheduler calls for identical reconcile', async () => {
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
          notification_id: `habit:same:${tomorrowIso}`,
          habit_id: 'same',
          habit_name: 'Same Habit',
          occurrence_date: tomorrowIso,
          reminder_time: '10:00:00',
        }
      ]
    };
    (remindersApi.fetchReminderPlan as jest.Mock).mockResolvedValue(plan);
    
    (Notifications.getAllScheduledNotificationsAsync as jest.Mock).mockResolvedValue([
      { identifier: `habit:same:${tomorrowIso}` }, // Already exists
    ]);

    await reconcile();

    expect(Notifications.cancelScheduledNotificationAsync).not.toHaveBeenCalled();
    expect(Notifications.scheduleNotificationAsync).not.toHaveBeenCalled();
  });

  it('serializes concurrent reconcile calls', async () => {
    (permissions.getPermissionStatus as jest.Mock).mockResolvedValue({ granted: true });
    
    let resolvePlan1: any;
    const planPromise1 = new Promise(r => resolvePlan1 = r);
    
    let resolvePlan2: any;
    const planPromise2 = new Promise(r => resolvePlan2 = r);

    (remindersApi.fetchReminderPlan as jest.Mock)
      .mockReturnValueOnce(planPromise1)
      .mockReturnValueOnce(planPromise2);
      
    (Notifications.getAllScheduledNotificationsAsync as jest.Mock).mockResolvedValue([]);

    // Fire two reconciles concurrently
    const p1 = reconcile();
    const p2 = reconcile();

    // Yield control so p1 can reach fetchReminderPlan
    await new Promise(r => setTimeout(r, 0));

    // Only one should have requested the plan so far
    expect(remindersApi.fetchReminderPlan).toHaveBeenCalledTimes(1);

    // Complete first reconcile
    resolvePlan1({ reminders: [] });
    
    // Yield to let the next queued reconcile start and hit fetchReminderPlan
    await new Promise(r => setTimeout(r, 0));
    // The second reconcile should now be queued and executing
    expect(remindersApi.fetchReminderPlan).toHaveBeenCalledTimes(2);
    
    // Complete second reconcile
    resolvePlan2({ reminders: [] });
    
    await Promise.all([p1, p2]);
  });
});

describe('clearAllHabitNotifications', () => {
  it('cancels all habit:* notifications on logout', async () => {
    (Notifications.getAllScheduledNotificationsAsync as jest.Mock).mockResolvedValue([
      { identifier: 'habit:1' },
      { identifier: 'habit:2' },
      { identifier: 'unrelated:1' },
    ]);

    await clearAllHabitNotifications();

    expect(Notifications.cancelScheduledNotificationAsync).toHaveBeenCalledWith('habit:1');
    expect(Notifications.cancelScheduledNotificationAsync).toHaveBeenCalledWith('habit:2');
    expect(Notifications.cancelScheduledNotificationAsync).not.toHaveBeenCalledWith('unrelated:1');
  });
});
