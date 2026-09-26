import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, ActivityIndicator, SafeAreaView, TouchableOpacity } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { getCalendarSummary, CalendarSummaryResponse } from '../api/calendar';
import { fetchOccurrences, Occurrence, updateOccurrence, OccurrenceStatus } from '../api/occurrences';
import { colors, typography, spacing } from '../theme';
import { format, addMonths, subMonths, startOfMonth, endOfMonth, eachDayOfInterval, isSameMonth, isSameDay, startOfWeek, endOfWeek, addDays, subDays, addWeeks, subWeeks } from 'date-fns';
import { v4 as uuidv4 } from 'uuid';

type ViewMode = 'DAILY' | 'WEEKLY' | 'MONTHLY';

export const CalendarScreen = ({ navigation }: any) => {
  const [viewMode, setViewMode] = useState<ViewMode>('MONTHLY');
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [calendarData, setCalendarData] = useState<CalendarSummaryResponse | null>(null);
  const [occurrences, setOccurrences] = useState<Occurrence[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async (dateToLoad: Date) => {
    try {
      setLoading(true);
      setError(null);
      const resCal = await getCalendarSummary(dateToLoad.getFullYear(), dateToLoad.getMonth() + 1);
      setCalendarData(resCal);
      
      const formattedDate = format(dateToLoad, 'yyyy-MM-dd');
      let startD = formattedDate;
      let endD = formattedDate;
      
      if (viewMode === 'WEEKLY') {
        startD = format(startOfWeek(dateToLoad, { weekStartsOn: 1 }), 'yyyy-MM-dd');
        endD = format(endOfWeek(dateToLoad, { weekStartsOn: 1 }), 'yyyy-MM-dd');
      }

      const resOcc = await fetchOccurrences(startD, endD);
      setOccurrences(resOcc.occurrences);
      
    } catch (err: any) {
      setError(err?.message || 'Failed to load calendar');
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(
    useCallback(() => {
      loadData(selectedDate);
    }, [selectedDate, viewMode])
  );
  
  const goPrevMonth = () => setSelectedDate(subMonths(selectedDate, 1));
  const goNextMonth = () => setSelectedDate(addMonths(selectedDate, 1));
  const goPrevWeek = () => setSelectedDate(subWeeks(selectedDate, 1));
  const goNextWeek = () => setSelectedDate(addWeeks(selectedDate, 1));
  const goPrevDay = () => setSelectedDate(subDays(selectedDate, 1));
  const goNextDay = () => setSelectedDate(addDays(selectedDate, 1));

  const handleMutation = async (occ: Occurrence, newStatus: OccurrenceStatus) => {
    const idempotencyKey = uuidv4();
    try {
      setOccurrences(prev => prev.map(o => o.id === occ.id ? { ...o, status: newStatus } : o));
      await updateOccurrence(occ.id, newStatus, idempotencyKey);
      loadData(selectedDate);
    } catch (error) {
      loadData(selectedDate);
    }
  };

  const getDaySummary = (dateStr: string) => {
    return calendarData?.days.find(d => d.date === dateStr);
  };

  const renderOccurrence = (occ: Occurrence) => {
    const isCompleted = occ.status === 'completed';
    const isSkipped = occ.status === 'skipped';
    const isMissed = occ.status === 'missed';
    const isPending = occ.status === 'pending';
    const todayStr = format(new Date(), 'yyyy-MM-dd');
    const isLocked = occ.occurrence_date < todayStr;

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
          </View>
        </View>

        {!isLocked && !isMissed && (
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
        {(isLocked || isMissed) && (
          <View style={styles.habitActions}>
             <Text style={styles.missedText}>
               {isMissed ? 'MISSED - LOCKED' : 'PAST - LOCKED'}
             </Text>
          </View>
        )}
      </TouchableOpacity>
    );
  };

  const renderDaily = () => {
    const dailyOccs = occurrences.filter(o => o.occurrence_date === format(selectedDate, 'yyyy-MM-dd'));
    const summary = getDaySummary(format(selectedDate, 'yyyy-MM-dd'));
    const pct = summary?.percent ?? 0;
    
    return (
      <View>
        <View style={styles.navRow}>
          <TouchableOpacity onPress={goPrevDay} style={styles.navBtn}><Text style={styles.navBtnText}>◀</Text></TouchableOpacity>
          <Text style={styles.navDateText}>{format(selectedDate, 'dd MMMM yyyy').toUpperCase()}</Text>
          <TouchableOpacity onPress={goNextDay} style={styles.navBtn}><Text style={styles.navBtnText}>▶</Text></TouchableOpacity>
        </View>
        <View style={styles.summaryBar}>
          <Text style={styles.summaryText}>{pct}% COMPLETE</Text>
        </View>
        <View style={styles.occList}>
          {dailyOccs.map(occ => renderOccurrence(occ))}
          {dailyOccs.length === 0 && <Text style={styles.emptyText}>No habits scheduled.</Text>}
        </View>
      </View>
    );
  };

  const renderWeekly = () => {
    const startD = startOfWeek(selectedDate, { weekStartsOn: 1 });
    const endD = endOfWeek(selectedDate, { weekStartsOn: 1 });
    const daysInWeek = eachDayOfInterval({ start: startD, end: endD });

    return (
      <View>
        <View style={styles.navRow}>
          <TouchableOpacity onPress={goPrevWeek} style={styles.navBtn}><Text style={styles.navBtnText}>◀</Text></TouchableOpacity>
          <Text style={styles.navDateText}>WEEK {format(startD, 'dd MMM')} - {format(endD, 'dd MMM')}</Text>
          <TouchableOpacity onPress={goNextWeek} style={styles.navBtn}><Text style={styles.navBtnText}>▶</Text></TouchableOpacity>
        </View>
        
        <View style={styles.weekGrid}>
          {daysInWeek.map(d => {
             const dStr = format(d, 'yyyy-MM-dd');
             const summary = getDaySummary(dStr);
             const isSel = isSameDay(d, selectedDate);
             return (
               <TouchableOpacity 
                 key={dStr} 
                 style={[styles.weekDayCard, isSel && styles.weekDayCardSel]}
                 onPress={() => setSelectedDate(d)}
               >
                 <Text style={styles.weekDayName}>{format(d, 'E').toUpperCase()}</Text>
                 <Text style={styles.weekDayNum}>{format(d, 'dd')}</Text>
                 <Text style={styles.weekDayPct}>{summary?.percent ?? 0}%</Text>
               </TouchableOpacity>
             );
          })}
        </View>
        <View style={styles.occList}>
          <Text style={styles.subLabel}>OCCURRENCES FOR {format(selectedDate, 'dd MMM').toUpperCase()}</Text>
          {occurrences.filter(o => o.occurrence_date === format(selectedDate, 'yyyy-MM-dd')).map(occ => renderOccurrence(occ))}
          {occurrences.filter(o => o.occurrence_date === format(selectedDate, 'yyyy-MM-dd')).length === 0 && <Text style={styles.emptyText}>No habits scheduled.</Text>}
        </View>
      </View>
    );
  };

  const renderMonthly = () => {
    const monthStart = startOfMonth(selectedDate);
    const monthEnd = endOfMonth(monthStart);
    const startDate = startOfWeek(monthStart, { weekStartsOn: 1 });
    const endDate = endOfWeek(monthEnd, { weekStartsOn: 1 });
    const dateFormat = "yyyy-MM-dd";
    const days = eachDayOfInterval({ start: startDate, end: endDate });

    const weekDays = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

    return (
      <View>
        <View style={styles.navRow}>
          <TouchableOpacity onPress={goPrevMonth} style={styles.navBtn}><Text style={styles.navBtnText}>◀</Text></TouchableOpacity>
          <Text style={styles.navDateText}>{format(selectedDate, 'MMMM yyyy').toUpperCase()}</Text>
          <TouchableOpacity onPress={goNextMonth} style={styles.navBtn}><Text style={styles.navBtnText}>▶</Text></TouchableOpacity>
        </View>

        <View style={styles.gridContainer}>
          <View style={styles.weekHeader}>
            {weekDays.map((d, i) => (
              <Text key={`header-${i}`} style={[styles.weekHeaderText, i === 6 && { color: colors.error }]}>{d}</Text>
            ))}
          </View>
          <View style={styles.daysGrid}>
            {days.map((day, i) => {
              const dStr = format(day, dateFormat);
              const isCurrentMonth = isSameMonth(day, monthStart);
              const summary = getDaySummary(dStr);
              let pct = summary?.percent ?? null;
              
              let bgStyle: any = styles.dayCellEmpty;
              if (isCurrentMonth) {
                if (pct === 100) bgStyle = styles.dayCellFull;
                else if (pct === 0) bgStyle = styles.dayCellMissed;
                else if (pct !== null) bgStyle = styles.dayCellPartial;
                else bgStyle = styles.dayCellNormal;
              }

              return (
                <TouchableOpacity 
                  key={dStr} 
                  style={[styles.dayCell, bgStyle, !isCurrentMonth && styles.dayCellMuted]}
                  onPress={() => {
                    setSelectedDate(day);
                    setViewMode('DAILY');
                  }}
                >
                  <Text style={[styles.dayCellText, !isCurrentMonth && styles.dayCellTextMuted]}>{format(day, 'dd')}</Text>
                  {isCurrentMonth && pct !== null && (
                    <View style={styles.dayCellDotContainer}>
                      {pct === 100 ? <View style={styles.fullDot} /> : 
                       pct === 0 ? <View style={styles.missedDot} /> : 
                       <View style={styles.partialDot} />}
                    </View>
                  )}
                </TouchableOpacity>
              );
            })}
          </View>
        </View>
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.header}>
        <View style={styles.headerTitleRow}>
          <View style={styles.squarePrimary} />
          <Text style={styles.headerTitle}>CALENDAR</Text>
        </View>
        <Text style={styles.sysViewBadge}>SYS.VIEW // 09</Text>
      </View>

      <View style={styles.viewSelector}>
        <TouchableOpacity style={[styles.viewBtn, viewMode === 'DAILY' && styles.viewBtnActive]} onPress={() => setViewMode('DAILY')}>
          <Text style={[styles.viewBtnText, viewMode === 'DAILY' && styles.viewBtnTextActive]}>DAILY</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.viewBtn, viewMode === 'WEEKLY' && styles.viewBtnActive]} onPress={() => setViewMode('WEEKLY')}>
          <Text style={[styles.viewBtnText, viewMode === 'WEEKLY' && styles.viewBtnTextActive]}>WEEKLY</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.viewBtn, viewMode === 'MONTHLY' && styles.viewBtnActive]} onPress={() => setViewMode('MONTHLY')}>
          <Text style={[styles.viewBtnText, viewMode === 'MONTHLY' && styles.viewBtnTextActive]}>MONTHLY</Text>
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {loading && !calendarData ? (
          <ActivityIndicator size="large" color={colors.primary} />
        ) : error ? (
          <Text style={{ color: colors.error }}>{error}</Text>
        ) : (
          <>
            {viewMode === 'DAILY' && renderDaily()}
            {viewMode === 'WEEKLY' && renderWeekly()}
            {viewMode === 'MONTHLY' && renderMonthly()}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.surface },
  header: {
    padding: spacing.md,
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
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
  viewSelector: {
    marginHorizontal: spacing.md,
    backgroundColor: colors['surface-container-lowest'],
    flexDirection: 'row',
    padding: 4,
    borderWidth: 1,
    borderColor: colors.outline,
    shadowColor: colors.primary,
    shadowOffset: { width: 4, height: 4 },
    shadowOpacity: 1,
    shadowRadius: 0,
    elevation: 0,
    marginBottom: spacing.md,
  },
  viewBtn: { flex: 1, paddingVertical: spacing.xs, alignItems: 'center' },
  viewBtnActive: {
    backgroundColor: colors['secondary-container'],
    shadowColor: colors.primary,
    shadowOffset: { width: 2, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 0,
    borderWidth: 1,
    borderColor: colors.outline,
  },
  viewBtnText: { ...typography.labelMd, color: colors['on-surface-variant'] },
  viewBtnTextActive: { color: colors['on-surface'], fontWeight: 'bold' },
  scrollContent: { paddingHorizontal: spacing.md, paddingBottom: spacing.xl },
  navRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: colors.primary,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
  },
  navBtn: { padding: spacing.xs, backgroundColor: colors.primary },
  navBtnText: { color: colors['on-primary'], fontSize: 20 },
  navDateText: { ...typography.titleSm, color: colors['on-primary'], letterSpacing: 1.5 },
  gridContainer: {
    marginTop: spacing.xs,
    backgroundColor: colors['surface-container-lowest'],
    padding: 8,
    borderWidth: 1,
    borderColor: colors.outline,
    shadowColor: colors.primary,
    shadowOffset: { width: 4, height: 4 },
    shadowOpacity: 1,
    shadowRadius: 0,
  },
  weekHeader: { flexDirection: 'row', backgroundColor: colors['surface-container-highest'], paddingVertical: 4 },
  weekHeaderText: { flex: 1, textAlign: 'center', ...typography.labelSm, color: colors.primary },
  daysGrid: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 4 },
  dayCell: {
    width: '14.28%',
    aspectRatio: 1,
    padding: 2,
  },
  dayCellNormal: { backgroundColor: colors['surface-container-low'], borderWidth: 1, borderColor: colors.surface },
  dayCellFull: { backgroundColor: colors['secondary-container'], borderWidth: 1, borderColor: colors.outline, shadowColor: colors.primary, shadowOffset: { width: 1, height: 1 }, shadowOpacity: 1, shadowRadius: 0 },
  dayCellMissed: { backgroundColor: colors['error-container'], borderWidth: 1, borderColor: colors.outline },
  dayCellPartial: { backgroundColor: colors['surface-container-high'], borderWidth: 1, borderColor: colors.outline },
  dayCellEmpty: { backgroundColor: colors['surface-container-low'], opacity: 0.35 },
  dayCellMuted: { opacity: 0.35 },
  dayCellText: { ...typography.labelSm, color: colors.primary },
  dayCellTextMuted: { color: colors['on-surface-variant'] },
  dayCellDotContainer: { flex: 1, justifyContent: 'flex-end', alignItems: 'flex-end', padding: 2 },
  fullDot: { width: 6, height: 6, backgroundColor: colors.primary },
  missedDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.error },
  partialDot: { width: 6, height: 6, backgroundColor: colors.primary, opacity: 0.5 },
  
  weekGrid: { flexDirection: 'row', justifyContent: 'space-between', marginTop: spacing.md },
  weekDayCard: {
    flex: 1, marginHorizontal: 2, backgroundColor: colors['surface-container-low'], paddingVertical: spacing.sm, alignItems: 'center', borderWidth: 1, borderColor: colors.outline
  },
  weekDayCardSel: {
    backgroundColor: colors['secondary-container'], shadowColor: colors.primary, shadowOffset: { width: 2, height: 2 }, shadowOpacity: 1, shadowRadius: 0,
  },
  weekDayName: { ...typography.labelSm, color: colors['on-surface-variant'] },
  weekDayNum: { ...typography.titleSm, color: colors.primary, marginVertical: 2 },
  weekDayPct: { ...typography.labelSm, color: colors.primary },

  summaryBar: {
    backgroundColor: colors['secondary-container'],
    padding: spacing.xs,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.outline,
    marginVertical: spacing.sm,
    shadowColor: colors.primary,
    shadowOffset: { width: 2, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 0,
  },
  summaryText: { ...typography.labelMd, color: colors['on-surface'], fontWeight: 'bold' },

  occList: { marginTop: spacing.md, gap: spacing.sm },
  subLabel: { ...typography.labelMd, color: colors['on-surface-variant'], marginBottom: spacing.xs },
  emptyText: { ...typography.bodyMd, color: colors['on-surface-variant'], textAlign: 'center', marginTop: spacing.md },

  habitCard: {
    backgroundColor: colors['surface-container-lowest'],
    padding: spacing.md,
    borderWidth: 2.5,
    borderColor: colors.primary,
    shadowColor: colors.primary,
    shadowOffset: { width: 4, height: 4 },
    shadowOpacity: 1,
    shadowRadius: 0,
    elevation: 0,
  },
  habitCardCompleted: { backgroundColor: colors['surface-container'], borderColor: colors.outline },
  habitTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  habitInfo: { flex: 1 },
  completedBadge: { backgroundColor: colors['secondary-container'], alignSelf: 'flex-start', paddingHorizontal: 8, paddingVertical: 4, marginBottom: 8, borderWidth: 1.5, borderColor: colors.primary },
  completedBadgeText: { ...typography.labelMd, color: colors.primary },
  habitName: { ...typography.titleSm, color: colors.primary, textTransform: 'uppercase' },
  habitNameStrikethrough: { textDecorationLine: 'line-through', color: colors['on-surface-variant'] },
  habitActions: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.md },
  actionBtnSkip: { flex: 1, backgroundColor: colors['surface-container-highest'], paddingVertical: 12, alignItems: 'center', borderWidth: 2, borderColor: colors.primary, shadowColor: colors.primary, shadowOffset: { width: 2, height: 2 }, shadowOpacity: 1, shadowRadius: 0 },
  actionBtnComplete: { flex: 2, backgroundColor: colors['secondary-container'], paddingVertical: 12, alignItems: 'center', borderWidth: 2, borderColor: colors.primary, shadowColor: colors.primary, shadowOffset: { width: 2, height: 2 }, shadowOpacity: 1, shadowRadius: 0 },
  actionBtnUndo: { flex: 1, backgroundColor: colors.surface, paddingVertical: 12, alignItems: 'center', borderWidth: 2, borderColor: colors.primary, shadowColor: colors.primary, shadowOffset: { width: 2, height: 2 }, shadowOpacity: 1, shadowRadius: 0 },
  actionBtnText: { ...typography.labelLg, color: colors.primary },
  missedText: { ...typography.labelLg, color: colors.error },
});
