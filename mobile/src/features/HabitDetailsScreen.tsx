import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, SafeAreaView, TouchableOpacity } from 'react-native';
import { getHabitStats, HabitStats } from '../api/stats';
import { colors, typography, spacing } from '../theme';
import { MaterialIcons } from '@expo/vector-icons';

export const HabitDetailsScreen = ({ route, navigation }: any) => {
  const { habitId, habitName } = route.params;
  const [data, setData] = useState<HabitStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getHabitStats(habitId);
      setData(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to load habit stats');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [habitId]);

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <MaterialIcons name="arrow-back" size={24} color={colors.primary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{habitName || 'HABIT DETAILS'}</Text>
      </View>
      
      {loading && !data ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      ) : error && !data ? (
        <View style={styles.centerContainer}>
          <Text style={{ color: colors.error }}>{error}</Text>
        </View>
      ) : (
        <View style={styles.content}>
          <View style={styles.statCard}>
            <Text style={styles.statLabel}>Current Streak</Text>
            <Text style={styles.statValue}>{data?.current_streak}</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statLabel}>Longest Streak</Text>
            <Text style={styles.statValue}>{data?.longest_streak}</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statLabel}>Total Completions</Text>
            <Text style={styles.statValue}>{data?.total_completions}</Text>
          </View>
        </View>
      )}
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
    flexDirection: 'row',
    alignItems: 'center',
  },
  backBtn: {
    marginRight: spacing.sm,
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
