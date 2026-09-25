import { apiClient } from './client';

export type OccurrenceStatus = 'pending' | 'completed' | 'skipped' | 'missed';

export interface Occurrence {
  id: string;
  habit_id: string;
  habit_name: string;
  occurrence_date: string;
  status: OccurrenceStatus;
  completed_at: string | null;
  reminder_time: string | null;
}

export interface Progress {
  completed: number;
  total: number;
  percent: number;
}

export interface TodayResponse {
  date: string;
  occurrences: Occurrence[];
  progress: Progress;
}

export const fetchToday = async (): Promise<TodayResponse> => {
  const response = await apiClient.get<TodayResponse>('/api/v1/today');
  return response.data;
};

export const updateOccurrence = async (
  id: string,
  status: OccurrenceStatus,
  idempotencyKey: string
): Promise<Occurrence> => {
  const response = await apiClient.put<Occurrence>(
    `/api/v1/occurrences/${id}`,
    { status },
    {
      headers: {
        'Idempotency-Key': idempotencyKey,
      },
    }
  );
  return response.data;
};
