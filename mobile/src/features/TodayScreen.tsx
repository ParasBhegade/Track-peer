import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, Image, SafeAreaView } from 'react-native';
import { fetchToday, updateOccurrence, TodayResponse, Occurrence } from '../api/occurrences';
import { colors, typography, spacing } from '../theme';
import 'react-native-get-random-values';
import { v4 as uuidv4 } from 'uuid';
import { MaterialIcons } from '@expo/vector-icons';

export const TodayScreen = ({ navigation }: any) => {
  const [data, setData] = useState<TodayResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchToday();
      setData(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to load today');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleMutation = async (occ: Occurrence, newStatus: Occurrence['status']) => {
    if (!data) return;
    const previousData = { ...data, occurrences: [...data.occurrences] };
    
    try {
      // Optimistic update
      const updatedOccs = data.occurrences.map(o => o.id === occ.id ? { ...o, status: newStatus } : o);
      const newCompleted = updatedOccs.filter(o => o.status === 'completed').length;
      const total = data.progress.total;
      const newPercent = total > 0 ? Math.round((newCompleted / total) * 100) : 0;
      
      setData({
        ...data,
        occurrences: updatedOccs,
        progress: {
          completed: newCompleted,
          total,
          percent: newPercent,
        }
      });

      const key = uuidv4();
      await updateOccurrence(occ.id, newStatus, key);
      
      // We could reload data here from backend to ensure perfect consistency, 
      // but optimistic UI is acceptable if it succeeds.
    } catch (err) {
      // Rollback
      setData(previousData);
      alert('Failed to update occurrence');
    }
  };

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
        <Text style={[styles.textLabel, { color: colors.error, marginBottom: 16 }]}>{error}</Text>
        <TouchableOpacity style={styles.primaryBtn} onPress={loadData}>
          <Text style={styles.primaryBtnText}>RETRY</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (!data) return null;

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Text style={styles.brandText}>HABIT TRACKER</Text>
          <Text style={styles.headerTitle}>HOME</Text>
        </View>
        <View style={styles.profileCircle}>
           {/* Fallback to simple icon if image missing */}
           <MaterialIcons name="person" size={24} color={colors.primary} />
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.titleSection}>
          <View style={styles.dateLabelRow}>
            <Text style={styles.dateLabelText}>[ {new Date(data.date).toDateString().toUpperCase()} ]</Text>
          </View>
          <Text style={styles.mainTitle}>TODAY</Text>
        </View>

        <View style={styles.progressCard}>
          <View style={styles.progressTop}>
            <View>
              <Text style={styles.metricObjective}>METRIC OBJECTIVE</Text>
              <View style={styles.metricFractions}>
                <Text style={styles.metricCompleted}>{String(data.progress.completed).padStart(2, '0')}</Text>
                <Text style={styles.metricTotal}> / {String(data.progress.total).padStart(2, '0')}</Text>
              </View>
            </View>
            <View style={styles.executionBox}>
              <Text style={styles.executionLabel}>EXECUTION</Text>
              <Text style={styles.executionPercent}>{data.progress.percent}%</Text>
            </View>
          </View>
          
          <View style={styles.progressBarGrid}>
             {Array.from({ length: Math.max(data.progress.total, 6) }).map((_, i) => {
               const isComplete = i < data.progress.completed;
               const isValid = i < data.progress.total;
               return (
                 <View key={i} style={[
                   styles.progressSegment, 
                   isComplete && styles.progressSegmentComplete,
                   !isValid && styles.progressSegmentInactive
                 ]} />
               );
             })}
          </View>
        </View>

        <View style={styles.sectionHeader}>
          <View style={styles.sectionTitleRow}>
            <View style={styles.blackDot} />
            <Text style={styles.sectionTitle}>ROUTINES & PROTOCOLS</Text>
          </View>
        </View>

        <View style={styles.habitsList}>
          {data.occurrences.map(occ => {
            const isCompleted = occ.status === 'completed';
            const isSkipped = occ.status === 'skipped';
            const isMissed = occ.status === 'missed';
            const isPending = occ.status === 'pending';

            return (
              <TouchableOpacity key={occ.id} style={[
                styles.habitCard,
                isCompleted && styles.habitCardCompleted
              ]}
              onPress={() => navigation.navigate('HabitDetails', { habitId: occ.habit_id, habitName: occ.habit_name })}
              activeOpacity={0.8}
              >
                <View style={styles.habitTop}>
                  <View style={styles.habitInfo}>
                    {isCompleted && (
                      <View style={styles.completedBadge}>
                        <Text style={styles.completedBadgeText}>✓ COMPLETED</Text>
                      </View>
                    )}
                    <Text style={[styles.habitName, isCompleted && styles.habitNameStrikethrough]}>
                      {occ.habit_name}
                    </Text>
                    <Text style={styles.habitMeta}>
                      {occ.reminder_time ? `REMINDER ${occ.reminder_time}` : 'NO REMINDER'}
                    </Text>
                  </View>
                  {isCompleted && (
                     <View style={styles.verifiedBox}>
                       <Text style={styles.verifiedText}>VERIFIED</Text>
                     </View>
                  )}
                </View>

                {!isMissed && (
                  <View style={styles.habitActions}>
                    {isPending && (
                      <>
                        <TouchableOpacity style={styles.actionBtnSkip} onPress={() => handleMutation(occ, 'skipped')}>
                          <Text style={styles.actionBtnText}>SKIP</Text>
                        </TouchableOpacity>
                        <TouchableOpacity style={styles.actionBtnComplete} onPress={() => handleMutation(occ, 'completed')}>
                          <Text style={styles.actionBtnText}>MARK COMPLETE</Text>
                        </TouchableOpacity>
                      </>
                    )}
                    {(isCompleted || isSkipped) && (
                       <TouchableOpacity style={styles.actionBtnUndo} onPress={() => handleMutation(occ, 'pending')}>
                         <Text style={styles.actionBtnText}>UNDO {isSkipped ? 'SKIP' : 'COMPLETION'}</Text>
                       </TouchableOpacity>
                    )}
                  </View>
                )}
                {isMissed && (
                  <View style={styles.habitActions}>
                     <Text style={styles.missedText}>MISSED - LOCKED</Text>
                  </View>
                )}
              </TouchableOpacity>
            );
          })}
        </View>

      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.background,
  },
  textLabel: {
    ...typography.labelLg,
    color: colors['on-surface'],
  },
  primaryBtn: {
    backgroundColor: colors['secondary-container'],
    borderWidth: 2.5,
    borderColor: colors.primary,
    paddingHorizontal: 24,
    paddingVertical: 12,
    shadowColor: colors.primary,
    shadowOffset: { width: 4, height: 4 },
    shadowOpacity: 1,
    shadowRadius: 0,
    elevation: 0,
  },
  primaryBtnText: {
    ...typography.labelLg,
    color: colors.primary,
  },
  header: {
    height: 64,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.margin,
    borderBottomWidth: 2.5,
    borderBottomColor: colors.primary,
    backgroundColor: colors.surface,
  },
  headerLeft: {
    flexDirection: 'column',
  },
  brandText: {
    ...typography.labelMd,
    color: colors.primary,
    textTransform: 'uppercase',
  },
  headerTitle: {
    ...typography.titleSm,
    textTransform: 'uppercase',
    color: colors['on-surface'],
  },
  profileCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 2.5,
    borderColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors['surface-container-highest'],
  },
  scrollContent: {
    padding: spacing.margin,
    paddingBottom: 80,
  },
  titleSection: {
    marginTop: spacing.md,
    marginBottom: spacing.lg,
  },
  dateLabelRow: {
    backgroundColor: colors['surface-container-highest'],
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderWidth: 2.5,
    borderColor: colors.primary,
    shadowColor: colors.primary,
    shadowOffset: { width: 2, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 0,
    elevation: 0,
    marginBottom: spacing.xs,
  },
  dateLabelText: {
    ...typography.labelMd,
    color: colors['on-surface'],
  },
  mainTitle: {
    ...typography.display,
    color: colors.primary,
  },
  progressCard: {
    backgroundColor: colors['surface-container-lowest'],
    padding: spacing.md,
    borderWidth: 2.5,
    borderColor: colors.primary,
    shadowColor: colors.primary,
    shadowOffset: { width: 5, height: 5 },
    shadowOpacity: 1,
    shadowRadius: 0,
    elevation: 0,
  },
  progressTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  metricObjective: {
    ...typography.labelSm,
    color: colors['on-surface-variant'],
    marginBottom: 4,
  },
  metricFractions: {
    flexDirection: 'row',
    alignItems: 'baseline',
  },
  metricCompleted: {
    ...typography.displayMobile,
    color: colors.primary,
  },
  metricTotal: {
    ...typography.titleSm,
    color: colors['on-surface-variant'],
    marginLeft: 8,
  },
  executionBox: {
    backgroundColor: colors['secondary-container'],
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderWidth: 2.5,
    borderColor: colors.primary,
    shadowColor: colors.primary,
    shadowOffset: { width: 2, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 0,
    alignItems: 'center',
  },
  executionLabel: {
    ...typography.labelSm,
    color: colors.primary,
  },
  executionPercent: {
    ...typography.headlineMd,
    color: colors.primary,
    marginTop: 2,
  },
  progressBarGrid: {
    flexDirection: 'row',
    height: 24,
    marginTop: spacing.md,
    borderWidth: 2.5,
    borderColor: colors.primary,
    backgroundColor: colors['surface-container-highest'],
  },
  progressSegment: {
    flex: 1,
    borderRightWidth: 2.5,
    borderRightColor: colors.primary,
    backgroundColor: colors['surface-container-highest'],
  },
  progressSegmentComplete: {
    backgroundColor: colors['secondary-container'],
  },
  progressSegmentInactive: {
    opacity: 0.4,
  },
  sectionHeader: {
    marginTop: spacing.xl,
    marginBottom: spacing.md,
  },
  sectionTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  blackDot: {
    width: 12,
    height: 12,
    backgroundColor: colors.primary,
    marginRight: spacing.sm,
  },
  sectionTitle: {
    ...typography.labelMd,
    color: colors.primary,
  },
  habitsList: {
    gap: spacing.md,
  },
  habitCard: {
    backgroundColor: colors['surface-container-lowest'],
    borderWidth: 2.5,
    borderColor: colors.primary,
    shadowColor: colors.primary,
    shadowOffset: { width: 4, height: 4 },
    shadowOpacity: 1,
    shadowRadius: 0,
    padding: spacing.md,
  },
  habitCardCompleted: {
    backgroundColor: colors['secondary-container'], // Used for completed states in Stitch reference
  },
  habitTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  habitInfo: {
    flex: 1,
  },
  completedBadge: {
    backgroundColor: colors.primary,
    alignSelf: 'flex-start',
    paddingHorizontal: 6,
    paddingVertical: 2,
    marginBottom: 4,
  },
  completedBadgeText: {
    ...typography.labelSm,
    color: colors['on-primary'],
  },
  habitName: {
    ...typography.headlineMd,
    color: colors.primary,
  },
  habitNameStrikethrough: {
    textDecorationLine: 'line-through',
    textDecorationStyle: 'solid',
  },
  habitMeta: {
    ...typography.bodySm,
    color: colors['on-surface-variant'],
    marginTop: 4,
    textTransform: 'uppercase',
    fontWeight: 'bold',
  },
  verifiedBox: {
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderWidth: 2.5,
    borderColor: colors['surface-container-lowest'],
    shadowColor: colors['surface-container-lowest'],
    shadowOffset: { width: 2, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 0,
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: 54,
  },
  verifiedText: {
    ...typography.labelSm,
    color: colors['on-primary'],
  },
  habitActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    marginTop: spacing.md,
    paddingTop: spacing.sm,
    borderTopWidth: 2.5,
    borderTopColor: colors.primary,
    gap: spacing.sm,
  },
  actionBtnComplete: {
    backgroundColor: colors['secondary-container'],
    borderWidth: 2.5,
    borderColor: colors.primary,
    paddingHorizontal: spacing.md,
    paddingVertical: 8,
    shadowColor: colors.primary,
    shadowOffset: { width: 3, height: 3 },
    shadowOpacity: 1,
    shadowRadius: 0,
  },
  actionBtnSkip: {
    backgroundColor: colors.surface,
    borderWidth: 2.5,
    borderColor: colors.primary,
    paddingHorizontal: spacing.md,
    paddingVertical: 8,
    shadowColor: colors.primary,
    shadowOffset: { width: 3, height: 3 },
    shadowOpacity: 1,
    shadowRadius: 0,
  },
  actionBtnUndo: {
    backgroundColor: colors['surface-container-highest'],
    borderWidth: 2.5,
    borderColor: colors.primary,
    paddingHorizontal: spacing.md,
    paddingVertical: 8,
    shadowColor: colors.primary,
    shadowOffset: { width: 3, height: 3 },
    shadowOpacity: 1,
    shadowRadius: 0,
  },
  actionBtnText: {
    ...typography.labelLg,
    color: colors.primary,
  },
  missedText: {
    ...typography.labelLg,
    color: colors.error,
  }
});
