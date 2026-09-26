import { apiClient } from "./client";

export interface CalendarDaySummary {
  date: string;
  scheduled: number;
  completed: number;
  percent: number | null;
}

export interface CalendarSummaryResponse {
  days: CalendarDaySummary[];
}

export async function getCalendarSummary(year: number, month: number): Promise<CalendarSummaryResponse> {
  const { data } = await apiClient.get<CalendarSummaryResponse>("/calendar/summary", {
    params: { year, month },
  });
  return data;
}
