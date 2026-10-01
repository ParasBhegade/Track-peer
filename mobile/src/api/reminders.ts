import { apiClient } from './client';

export interface ReminderItem {
  notification_id: string;
  habit_id: string;
  habit_name: string;
  occurrence_date: string;
  reminder_time: string;
}

export interface ReminderPlanResponse {
  timezone: string;
  from: string;
  to: string;
  reminders: ReminderItem[];
}

export const fetchReminderPlan = async (): Promise<ReminderPlanResponse> => {
  const response = await apiClient.get<ReminderPlanResponse>('/api/v1/reminders/plan');
  return response.data;
};
