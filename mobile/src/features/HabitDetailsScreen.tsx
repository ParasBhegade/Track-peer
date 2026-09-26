import React, { useState, useCallback } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, SafeAreaView, TouchableOpacity, ScrollView } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
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

  useFocusEffect(
    useCallback(() => {
      loadData();
    }, [habitId])
  );

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.header}>
        <View style={styles.headerTitleRow}>
          <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
            <MaterialIcons name="arrow-back" size={24} color={colors.primary} />
          </TouchableOpacity>
          <View>
            <Text style={styles.sysViewBadge}>HABIT TRACKER</Text>
            <Text style={styles.headerTitle}>Habit Details</Text>
          </View>
        </View>
      </View>
      
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {loading && !data ? (
          <View style={styles.centerContainer}>
            <ActivityIndicator size="large" color={colors.primary} />
          </View>
        ) : error && !data ? (
          <View style={styles.centerContainer}>
            <Text style={{ color: colors.error }}>{error}</Text>
          </View>
        ) : (
          <>
            <View style={styles.heroSection}>
              <View style={styles.tagsRow}>
                <View style={styles.tagPrimary}>
                  <Text style={styles.tagPrimaryText}>ACTIVE PROTOCOL</Text>
                </View>
                <View style={styles.tagSecondary}>
                  <Text style={styles.tagSecondaryText}>HABIT DETAILS</Text>
                </View>
              </View>
              <Text style={styles.heroTitle}>{habitName || 'HABIT DETAILS'}</Text>
            </View>

            <View style={styles.sectionHeader}>
              <Text style={styles.sectionTitle}>TELEMETRY MATRIX</Text>
              <Text style={styles.sectionBadge}>SYS.REV 24.09</Text>
            </View>

            <View style={styles.grid}>
              <View style={[styles.statCard, { backgroundColor: colors['secondary-container'] }]}>
                <View style={styles.cardTop}>
                  <Text style={[styles.cardLabel, { color: colors['on-secondary-container'] }]}>CURRENT STREAK</Text>
                  <MaterialIcons name="bolt" size={20} color={colors['on-surface']} />
                </View>
                <View style={styles.cardMid}>
                  <Text style={[styles.cardValue, { color: colors['on-surface'] }]}>{data?.current_streak}</Text>
                  <Text style={[styles.cardTitle, { color: colors['on-surface'] }]}>DAYS</Text>
                </View>
              </View>

              <View style={[styles.statCard, { backgroundColor: colors['surface-container-lowest'] }]}>
                <View style={styles.cardTop}>
                  <Text style={styles.cardLabel}>PEAK BENCHMARK</Text>
                  <MaterialIcons name="military-tech" size={20} color={colors['on-surface-variant']} />
                </View>
                <View style={styles.cardMid}>
                  <Text style={styles.cardValue}>{data?.longest_streak}</Text>
                  <Text style={[styles.cardTitle, { color: colors['on-surface-variant'] }]}>DAYS</Text>
                </View>
              </View>

              <View style={[styles.statCard, { backgroundColor: colors.primary, width: '100%' }]}>
                <View style={styles.cardTop}>
                  <Text style={[styles.cardLabel, { color: colors['on-primary-container'] }]}>VERIFIED RUNS</Text>
                  <MaterialIcons name="verified" size={20} color={colors['on-primary-container']} />
                </View>
                <View style={styles.cardMid}>
                  <Text style={[styles.cardValue, { color: colors['on-primary'] }]}>{data?.total_completions}</Text>
                  <Text style={[styles.cardTitle, { color: colors['on-primary-container'] }]}>TOTAL</Text>
                </View>
              </View>
            </View>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.surface },
  centerContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: spacing.md },
  header: {
    padding: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.outline,
    backgroundColor: colors.surface,
    opacity: 0.9,
  },
  headerTitleRow: { flexDirection: 'row', alignItems: 'center' },
  backBtn: {
    marginRight: spacing.sm,
    width: 40, height: 40,
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: 4,
  },
  sysViewBadge: {
    ...typography.labelMd,
    color: colors.primary,
    textTransform: 'uppercase',
    letterSpacing: 1.5,
  },
  headerTitle: {
    ...typography.titleSm,
    color: colors['on-surface'],
    textTransform: 'uppercase',
  },
  scrollContent: { paddingHorizontal: spacing.md, paddingBottom: spacing.xl },
  
  heroSection: { marginVertical: spacing.lg, backgroundColor: colors['surface-container-lowest'], padding: spacing.md, shadowColor: colors.primary, shadowOffset: { width: 4, height: 4 }, shadowOpacity: 1, shadowRadius: 0 },
  tagsRow: { flexDirection: 'row', gap: spacing.xs, marginBottom: spacing.xs, flexWrap: 'wrap' },
  tagPrimary: { backgroundColor: colors.primary, paddingHorizontal: 8, paddingVertical: 4 },
  tagPrimaryText: { ...typography.labelSm, color: colors['on-primary'], textTransform: 'uppercase' },
  tagSecondary: { backgroundColor: colors['secondary-container'], paddingHorizontal: 8, paddingVertical: 4 },
  tagSecondaryText: { ...typography.labelSm, color: colors['on-surface'], textTransform: 'uppercase' },
  heroTitle: {
    fontFamily: 'SpaceGrotesk_700Bold',
    fontSize: 36,
    lineHeight: 40,
    letterSpacing: -0.03,
    color: colors.primary,
    textTransform: 'uppercase',
    marginTop: spacing.xs
  },

  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.sm },
  sectionTitle: { ...typography.labelMd, color: colors.primary, textTransform: 'uppercase', letterSpacing: 1.5 },
  sectionBadge: { ...typography.labelSm, color: colors['on-surface-variant'], textTransform: 'uppercase' },

  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  statCard: {
    width: '48%',
    padding: spacing.md,
    shadowColor: colors.primary,
    shadowOffset: { width: 4, height: 4 },
    shadowOpacity: 1,
    shadowRadius: 0,
    borderWidth: 1,
    borderColor: colors.outline,
    justifyContent: 'space-between',
    minHeight: 110,
    marginBottom: spacing.xs
  },
  cardTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  cardLabel: { ...typography.labelSm, color: colors['on-surface-variant'], textTransform: 'uppercase', letterSpacing: 1.5, fontWeight: 'bold' },
  cardMid: { flexDirection: 'row', alignItems: 'baseline', gap: spacing.xs, marginTop: spacing.md },
  cardValue: { fontFamily: 'SpaceGrotesk_700Bold', fontSize: 48, lineHeight: 52, letterSpacing: -0.04, color: colors.primary },
  cardTitle: { ...typography.labelMd, color: colors.primary, textTransform: 'uppercase', fontWeight: 'bold' },
});
