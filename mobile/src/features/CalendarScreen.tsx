import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, ActivityIndicator, SafeAreaView } from 'react-native';
import { getCalendarSummary, CalendarSummaryResponse } from '../api/calendar';
import { colors, typography, spacing } from '../theme';

export const CalendarScreen = () => {
  const [data, setData] = useState<CalendarSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const now = new Date();
      const res = await getCalendarSummary(now.getFullYear(), now.getMonth() + 1);
      setData(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to load calendar');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading && !data) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  if (error && !data) {
    return (
      <View style={styles.centerContainer}>
        <Text style={{ color: colors.error }}>{error}</Text>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>CALENDAR</Text>
      </View>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {data?.days.map((day) => (
          <View key={day.date} style={styles.dayCard}>
            <Text style={styles.dateText}>{day.date}</Text>
            <Text style={styles.statText}>Scheduled: {day.scheduled}</Text>
            <Text style={styles.statText}>Completed: {day.completed}</Text>
            <Text style={styles.statText}>
              Score: {day.percent !== null ? `${day.percent}%` : 'N/A'}
            </Text>
          </View>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.surface,
  },
  safeArea: {
    flex: 1,
    backgroundColor: colors.surface,
  },
  header: {
    padding: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.outline,
  },
  headerTitle: {
    ...typography.headlineMd,
    color: colors.primary,
  },
  scrollContent: {
    padding: spacing.md,
    gap: spacing.sm,
  },
  dayCard: {
    padding: spacing.md,
    backgroundColor: colors['surface-container'],
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.outline,
  },
  dateText: {
    ...typography.titleSm,
    color: colors['on-surface'],
    marginBottom: spacing.xs,
  },
  statText: {
    ...typography.bodyMd,
    color: colors['on-surface-variant'],
  },
});
