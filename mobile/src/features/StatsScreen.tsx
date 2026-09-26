import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, SafeAreaView } from 'react-native';
import { getStatsOverview, AccountStats } from '../api/stats';
import { colors, typography, spacing } from '../theme';

export const StatsScreen = () => {
  const [data, setData] = useState<AccountStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getStatsOverview();
      setData(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to load stats');
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
        <Text style={styles.headerTitle}>STATISTICS</Text>
      </View>
      <View style={styles.content}>
        <View style={styles.statCard}>
          <Text style={styles.statLabel}>Active Habits</Text>
          <Text style={styles.statValue}>{data?.total_active_habits}</Text>
        </View>
        <View style={styles.statCard}>
          <Text style={styles.statLabel}>Best Streak</Text>
          <Text style={styles.statValue}>{data?.best_current_streak}</Text>
        </View>
        <View style={styles.statCard}>
          <Text style={styles.statLabel}>Total Completions</Text>
          <Text style={styles.statValue}>{data?.total_lifetime_completions}</Text>
        </View>
        <View style={styles.statCard}>
          <Text style={styles.statLabel}>Weekly Completion</Text>
          <Text style={styles.statValue}>
            {data?.weekly_completion_percent !== null ? `${data?.weekly_completion_percent}%` : 'N/A'}
          </Text>
        </View>
      </View>
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
  content: {
    padding: spacing.md,
    gap: spacing.md,
  },
  statCard: {
    padding: spacing.lg,
    backgroundColor: colors['surface-container'],
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.outline,
    alignItems: 'center',
  },
  statLabel: {
    ...typography.bodyMd,
    color: colors['on-surface-variant'],
    marginBottom: spacing.xs,
  },
  statValue: {
    ...typography.headlineLg,
    color: colors.primary,
  },
});
