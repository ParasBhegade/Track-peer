import * as Notifications from 'expo-notifications';
import { fetchReminderPlan } from '../api/reminders';
import { getPermissionStatus, configureAndroidChannel } from './permissions';
import { planToTriggers } from './planToTriggers';

let isReconciling = false;
let queuedReconcile = false;

/**
 * Ensures channel is configured before scheduling on Android.
 */
let channelConfigured = false;
async function ensureChannel() {
  if (!channelConfigured) {
    await configureAndroidChannel();
    channelConfigured = true;
  }
}

/**
 * Core reconcile logic that actually performs the scheduling.
 */
async function performReconcile() {
  try {
    // 1. Check permission
    const status = await getPermissionStatus();
    if (!status.granted) {
      return; // "no_permission makes zero scheduler calls"
    }

    await ensureChannel();

    // 2. Fetch the plan
    const plan = await fetchReminderPlan();

    // 3. Compute desired triggers
    const desiredTriggers = planToTriggers(plan, new Date());

    // 4. Fetch currently scheduled notifications
    const existingRequests = await Notifications.getAllScheduledNotificationsAsync();
    
    // filter habit:* notifications only
    const existingHabitRequests = existingRequests.filter(req => req.identifier.startsWith('habit:'));

    // 5. Cancel (existing - desired)
    const desiredIds = new Set(desiredTriggers.map(t => t.id));
    for (const existing of existingHabitRequests) {
      if (!desiredIds.has(existing.identifier)) {
        await Notifications.cancelScheduledNotificationAsync(existing.identifier);
      }
    }

    // 6. Schedule (desired - existing)
    const existingIds = new Set(existingHabitRequests.map(req => req.identifier));
    for (const desired of desiredTriggers) {
      if (!existingIds.has(desired.id)) {
        await Notifications.scheduleNotificationAsync({
          identifier: desired.id,
          content: {
            title: desired.title,
            body: desired.body,
            data: desired.data,
          },
          trigger: {
            type: Notifications.SchedulableTriggerInputTypes.DATE,
            date: desired.fireAt,
          },
        });
      }
    }
  } catch (err: any) {
    // Note: If this fails with 401, the API client should handle token expiry/redirects
    // depending on the auth layer setup (or if unsupported, fail gracefully).
    console.error('Reconcile failed', err);
  }
}

/**
 * Serialized reconciliation entry point.
 * Ensures overlapping calls do not interleave.
 * Exactly one follow-up reconcile is queued if requested while already running.
 */
export async function reconcile(): Promise<void> {
  if (isReconciling) {
    queuedReconcile = true;
    return;
  }

  isReconciling = true;

  try {
    await performReconcile();
  } finally {
    isReconciling = false;
    
    if (queuedReconcile) {
      queuedReconcile = false;
      // We explicitly DO NOT await here so the current caller is unblocked,
      // but we schedule the next iteration of the serialized queue.
      // Alternatively, we can await to block until the queue is completely drained.
      // To strictly guarantee "A completes -> exactly one follow-up B", 
      // recursive await is acceptable.
      await reconcile();
    }
  }
}

/**
 * Logout utility: explicitly cancels all habit:* notifications.
 */
export async function clearAllHabitNotifications(): Promise<void> {
  const existingRequests = await Notifications.getAllScheduledNotificationsAsync();
  const existingHabitRequests = existingRequests.filter(req => req.identifier.startsWith('habit:'));
  
  for (const existing of existingHabitRequests) {
    await Notifications.cancelScheduledNotificationAsync(existing.identifier);
  }
}
