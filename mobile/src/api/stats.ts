import { apiClient } from "./client";

export interface AccountStats {
  total_active_habits: number;
  weekly_completion_percent: number | null;
  best_current_streak: number;
  total_lifetime_completions: number;
}

export interface HabitStats {
  current_streak: number;
  longest_streak: number;
  total_completions: number;
  weekly_completion_percent: number | null;
  monthly_completion_percent: number | null;
}

export async function getStatsOverview(): Promise<AccountStats> {
  const { data } = await apiClient.get<AccountStats>("/stats/overview");
  return data;
}

export async function getHabitStats(habitId: string): Promise<HabitStats> {
  const { data } = await apiClient.get<HabitStats>(`/habits/${habitId}/stats`);
  return data;
}
