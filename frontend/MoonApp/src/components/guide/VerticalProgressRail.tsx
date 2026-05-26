import React from 'react';
import { StyleSheet, View } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import { COLORS } from '../../constants/colors';
import type { DecisionPoint } from '../../types/route';

interface Props {
  dpList: DecisionPoint[];
  currentIndex: number;
}

const COLOR_PASSED = '#34C759';
const COLOR_UPCOMING = '#B4B2A9';
const COLOR_TRACK_UPCOMING = '#E0E0E0';

export default function VerticalProgressRail({ dpList, currentIndex }: Props) {
  if (!dpList || dpList.length === 0) { return null; }

  const total = dpList.length;
  const clampedIndex = Math.max(0, Math.min(currentIndex, total));
  const lastIndex = total - 1;

  const renderMarker = (index: number) => {
    const isPassed = index < clampedIndex;
    const isCurrent = index === clampedIndex;
    const isStart = index === 0;
    const isEnd = index === lastIndex;

    if (isCurrent) {
      return (
        <View key={`m-${index}`} style={styles.currentOuter}>
          <View style={styles.currentInner} />
        </View>
      );
    }

    if (isPassed) {
      if (isStart) {
        return (
          <View key={`m-${index}`} style={styles.passedIconMarker}>
            <Icon name="checkmark" size={9} color="#FFFFFF" />
          </View>
        );
      }
      return <View key={`m-${index}`} style={styles.passedDot} />;
    }

    if (isEnd) {
      return (
        <View key={`m-${index}`} style={styles.upcomingIconMarker}>
          <Icon name="flag-outline" size={7} color="#888780" />
        </View>
      );
    }
    return <View key={`m-${index}`} style={styles.upcomingDot} />;
  };

  return (
    <View style={styles.container} pointerEvents="none">
      {dpList.map((_, i) => {
        const elements = [renderMarker(i)];
        if (i < lastIndex) {
          const segmentPassed = i < clampedIndex;
          elements.push(
            <View
              key={`s-${i}`}
              style={[
                styles.segment,
                { backgroundColor: segmentPassed ? COLOR_PASSED : COLOR_TRACK_UPCOMING },
              ]}
            />,
          );
        }
        return elements;
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    left: 12,
    top: '50%',
    transform: [{ translateY: -120 }],
    width: 14,
    height: 240,
    alignItems: 'center',
    flexDirection: 'column',
  },
  segment: {
    flex: 1,
    width: 3,
    marginVertical: -1,
  },
  passedDot: {
    width: 11,
    height: 11,
    borderRadius: 5.5,
    backgroundColor: COLOR_PASSED,
  },
  passedIconMarker: {
    width: 14,
    height: 14,
    borderRadius: 7,
    backgroundColor: COLOR_PASSED,
    alignItems: 'center',
    justifyContent: 'center',
  },
  upcomingDot: {
    width: 11,
    height: 11,
    borderRadius: 5.5,
    backgroundColor: '#FFFFFF',
    borderWidth: 2,
    borderColor: COLOR_UPCOMING,
  },
  upcomingIconMarker: {
    width: 14,
    height: 14,
    borderRadius: 7,
    backgroundColor: '#FFFFFF',
    borderWidth: 2,
    borderColor: COLOR_UPCOMING,
    alignItems: 'center',
    justifyContent: 'center',
  },
  currentOuter: {
    width: 16,
    height: 16,
    borderRadius: 8,
    borderWidth: 3,
    borderColor: COLORS.primary,
    backgroundColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 4,
    shadowColor: COLORS.primary,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
  },
  currentInner: {
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: COLORS.primary,
  },
});
