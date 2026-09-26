import React, { useState, useCallback } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, SafeAreaView, TouchableOpacity, ScrollView } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { getStatsOverview, AccountStats } from '../api/stats';
import { colors, typography, spacing } from '../theme';
import { MaterialIcons } from '@expo/vector-icons';

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

  useFocusEffect(
    useCallback(() => {
      loadData();
    }, [])
  );

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.header}>
        <View style={styles.headerTitleRow}>
          <View style={styles.squarePrimary} />
          <Text style={styles.headerTitle}>STATISTICS</Text>
        </View>
        <Text style={styles.sysViewBadge}>SYS.VIEW // 09</Text>
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
              <View style={styles.heroBadge}>
                <MaterialIcons name="analytics" size={16} color={colors['on-surface']} />
                <Text style={styles.heroBadgeText}>Audit Log // Telemetry</Text>
              </View>
              <Text style={styles.heroTitle}>THE NUMBERS.</Text>
              <Text style={styles.heroSubtitle}>NO FLUFF. OBJECTIVE PERFORMANCE DATA.</Text>
            </View>

            <View style={styles.grid}>
              <View style={[styles.statCard, { backgroundColor: colors['secondary-container'] }]}>
                <View style={styles.cardTop}>
                  <Text style={[styles.cardLabel, { color: colors['on-secondary-container'] }]}>01 // WK</Text>
                  <MaterialIcons name="donut-large" size={20} color={colors.primary} />
                </View>
                <View style={styles.cardMid}>
                  <Text style={styles.cardValue}>
                    {data?.weekly_completion_percent !== null ? `${data?.weekly_completion_percent}%` : 'N/A'}
                  </Text>
                  <Text style={styles.cardTitle}>WEEKLY COMPLETION</Text>
                </View>
                <Text style={[styles.cardFooter, { color: colors['on-secondary-container'] }]}>7-Day Roll</Text>
              </View>

              <View style={[styles.statCard, { backgroundColor: colors['surface-container-lowest'] }]}>
                <View style={styles.cardTop}>
                  <Text style={styles.cardLabel}>02 // ACT</Text>
                  <MaterialIcons name="fact-check" size={20} color={colors.primary} />
                </View>
                <View style={styles.cardMid}>
                  <Text style={styles.cardValue}>{data?.total_active_habits}</Text>
                  <Text style={styles.cardTitle}>ACTIVE HABITS</Text>
                </View>
                <Text style={styles.cardFooter}>Currently Tracked</Text>
              </View>

              <View style={[styles.statCard, { backgroundColor: colors['surface-container-lowest'] }]}>
                <View style={styles.cardTop}>
                  <Text style={styles.cardLabel}>03 // AGG</Text>
                  <MaterialIcons name="verified" size={20} color={colors.primary} />
                </View>
                <View style={styles.cardMid}>
                  <Text style={styles.cardValue}>{data?.total_lifetime_completions}</Text>
                  <Text style={styles.cardTitle}>TOTAL COMPLETED</Text>
                </View>
                <Text style={styles.cardFooter}>All-time verified</Text>
              </View>

              <View style={[styles.statCard, { backgroundColor: colors.primary }]}>
                <View style={styles.cardTop}>
                  <Text style={[styles.cardLabel, { color: colors['on-primary-container'] }]}>04 // PEAK</Text>
                  <MaterialIcons name="local-fire-department" size={20} color={colors['secondary-container']} />
                </View>
                <View style={styles.cardMid}>
                  <Text style={[styles.cardValue, { color: colors['secondary-container'] }]}>{data?.best_current_streak}</Text>
                  <Text style={[styles.cardTitle, { color: colors['on-primary'] }]}>BEST STREAK</Text>
                </View>
                <Text style={[styles.cardFooter, { color: colors['on-primary-container'] }]}>Global Max</Text>
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
  centerContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: {
    padding: spacing.md,
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    backgroundColor: colors.surface,
  },
  headerTitleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  squarePrimary: { width: 12, height: 12, backgroundColor: colors.primary },
  headerTitle: {
    fontFamily: 'SpaceGrotesk_700Bold',
    fontSize: 26,
    lineHeight: 30,
    letterSpacing: -0.02,
    color: colors.primary,
    textTransform: 'uppercase',
  },
  sysViewBadge: {
    ...typography.labelSm,
    backgroundColor: colors['surface-container-high'],
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
    color: colors['on-surface-variant'],
  },
  scrollContent: { paddingHorizontal: spacing.md, paddingBottom: spacing.xl },
  heroSection: { marginVertical: spacing.md },
  heroBadge: { 
    flexDirection: 'row', 
    alignItems: 'center', 
    gap: 4, 
    backgroundColor: colors['secondary-container'], 
    paddingHorizontal: spacing.sm, 
    paddingVertical: 4, 
    alignSelf: 'flex-start',
    shadowColor: colors.primary,
    shadowOffset: { width: 2, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 0,
    marginBottom: spacing.sm
  },
  heroBadgeText: { ...typography.labelSm, color: colors['on-surface'], textTransform: 'uppercase', letterSpacing: 1 },
  heroTitle: {
    fontFamily: 'SpaceGrotesk_700Bold',
    fontSize: 36,
    lineHeight: 40,
    letterSpacing: -0.03,
    color: colors.primary,
    textTransform: 'uppercase'
  },
  heroSubtitle: {
    ...typography.labelMd,
    color: colors['on-surface-variant'],
    textTransform: 'uppercase',
    marginTop: spacing.xs,
    letterSpacing: 1
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    gap: spacing.sm,
    marginBottom: spacing.lg
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
    minHeight: 160
  },
  cardTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  cardLabel: { ...typography.labelSm, color: colors['on-surface-variant'], textTransform: 'uppercase', letterSpacing: 1.5 },
  cardMid: { marginVertical: spacing.sm },
  cardValue: { fontFamily: 'SpaceGrotesk_700Bold', fontSize: 36, lineHeight: 40, letterSpacing: -0.03, color: colors.primary },
  cardTitle: { ...typography.labelSm, color: colors.primary, textTransform: 'uppercase', marginTop: 4, fontWeight: 'bold' },
  cardFooter: { ...typography.bodySm, color: colors['on-surface-variant'], fontWeight: '600', textTransform: 'uppercase' },
});
