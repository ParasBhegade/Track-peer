import React from 'react';
// @ts-ignore
import renderer, { act } from 'react-test-renderer';

jest.mock('uuid', () => ({ v4: () => 'mock-uuid' }));
jest.mock('expo-notifications', () => ({}));

import { CalendarScreen } from '../CalendarScreen';
import { getCalendarSummary } from '../../api/calendar';
import { fetchOccurrences } from '../../api/occurrences';
import { format, subMonths, addMonths } from 'date-fns';

jest.mock('react-native', () => {
  return {
    View: 'View',
    Text: 'Text',
    TouchableOpacity: 'TouchableOpacity',
    ScrollView: 'ScrollView',
    SafeAreaView: 'SafeAreaView',
    StyleSheet: { create: () => ({}) },
    Platform: { OS: 'ios' },
    ActivityIndicator: 'ActivityIndicator'
  };
});
jest.mock('@expo/vector-icons', () => ({
  Ionicons: 'Ionicons'
}));
jest.mock('../../api/calendar');
jest.mock('../../api/occurrences');

// Mock navigation
const mockNavigation = {
  navigate: jest.fn(),
};

let focusEffectCallback: any = null;

jest.mock('@react-navigation/native', () => {
  const { useEffect } = require('react');
  return {
    useFocusEffect: jest.fn((callback) => {
      focusEffectCallback = callback;
      useEffect(() => {
        callback();
      }, [callback]);
    }),
  };
});

describe('CalendarScreen Navigation Regression', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (getCalendarSummary as jest.Mock).mockResolvedValue({ days: [], streak: 0 });
    (fetchOccurrences as jest.Mock).mockResolvedValue({ occurrences: [] });
    focusEffectCallback = null;
  });

  const findByText = (root: any, text: string) => {
    const nodes = root.findAll((node: any) => node.type === 'Text' && node.children && node.children.join('') === text);
    return nodes.length > 0 ? nodes[0] : null;
  };

  const pressElement = (element: any) => {
    act(() => {
      element.props.onPress();
    });
  };

  it('Requirement 10: current month -> previous month -> remains previous month after data refresh', async () => {
    let root: any;
    await act(async () => {
      root = renderer.create(<CalendarScreen navigation={mockNavigation} />);
      await new Promise(process.nextTick);
    });

    // Initial render should be the current month
    const currentMonthLabel = format(new Date(), 'MMMM yyyy').toUpperCase();
    expect(findByText(root.root, currentMonthLabel)).toBeTruthy();

    // Tap Previous Month (◀)
    const prevButton = findByText(root.root, '◀')?.parent; // TouchableOpacity is parent
    expect(prevButton).toBeTruthy();
    pressElement(prevButton);
    
    // Should now be previous month
    const prevMonthDate = subMonths(new Date(), 1);
    const prevMonthLabel = format(prevMonthDate, 'MMMM yyyy').toUpperCase();
    expect(findByText(root.root, prevMonthLabel)).toBeTruthy();

    // Simulate a data refresh / focus effect triggered again 
    act(() => {
      if (focusEffectCallback) focusEffectCallback();
    });

    // Because userInteracted is now true, the effect won't reset it to current month.
    expect(findByText(root.root, prevMonthLabel)).toBeTruthy();
  });

  it('Requirement 11: multiple consecutive previous-month navigations', async () => {
    let root: any;
    await act(async () => {
      root = renderer.create(<CalendarScreen navigation={mockNavigation} />);
      await new Promise(process.nextTick);
    });
    
    const prevButton = findByText(root.root, '◀')?.parent;
    
    // Tap Prev 3 times
    pressElement(prevButton);
    pressElement(prevButton);
    pressElement(prevButton);

    const expectedDate = subMonths(new Date(), 3);
    const expectedLabel = format(expectedDate, 'MMMM yyyy').toUpperCase();

    expect(findByText(root.root, expectedLabel)).toBeTruthy();
  });

  it('Requirement 12: Verify next-month navigation still works', async () => {
    let root: any;
    await act(async () => {
      root = renderer.create(<CalendarScreen navigation={mockNavigation} />);
      await new Promise(process.nextTick);
    });
    
    const nextButton = findByText(root.root, '▶')?.parent;
    pressElement(nextButton);

    const expectedDate = addMonths(new Date(), 1);
    const expectedLabel = format(expectedDate, 'MMMM yyyy').toUpperCase();

    expect(findByText(root.root, expectedLabel)).toBeTruthy();
  });
});
