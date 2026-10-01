import { ReminderPlanResponse } from '../api/reminders';

export interface NotificationTrigger {
  id: string;
  fireAt: Date;
  title: string;
  body: string;
  data: {
    habit_id: string;
    occurrence_date: string;
    screen: string;
  };
}

/**
 * Pure function to convert a backend reminder plan into a list of local notification triggers.
 * It combines dates and times, drops reminders in the past, sorts by soonest first,
 * and truncates to the global limit of 60 across all habits.
 */
export function planToTriggers(plan: ReminderPlanResponse, now: Date): NotificationTrigger[] {
  const triggers: NotificationTrigger[] = [];

  for (const reminder of plan.reminders) {
    // Construct local Date object using device timezone directly
    // The ISO 8601 local format without Z gets parsed in local time.
    const fireAt = new Date(`${reminder.occurrence_date}T${reminder.reminder_time}`);
    
    // Drop triggers that are already in the past
    if (fireAt <= now) {
      continue;
    }
    
    triggers.push({
      id: reminder.notification_id,
      fireAt,
      title: reminder.habit_name,
      body: "Time for your habit.",
      data: {
        habit_id: reminder.habit_id,
        occurrence_date: reminder.occurrence_date,
        screen: "today",
      },
    });
  }

  // Sort soonest-first
  triggers.sort((a, b) => a.fireAt.getTime() - b.fireAt.getTime());

  // Truncate globally to 60 limit
  return triggers.slice(0, 60);
}
