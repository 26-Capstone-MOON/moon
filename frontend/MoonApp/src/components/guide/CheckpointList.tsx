import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import { COLORS } from '../../constants/colors';
import type { DecisionPoint } from '../../types/route';

interface Props {
  dpList: DecisionPoint[];
  currentIndex: number;
}

export default function CheckpointList({ dpList, currentIndex }: Props) {
  return (
    <View style={styles.container}>
      {dpList.map((dp, index) => {
        const isPassed = index < currentIndex;
        const isCurrent = index === currentIndex;

        return (
          <View key={dp.dpId} style={styles.row}>
            <View style={styles.left}>
              <View style={[
                styles.dot,
                isPassed && styles.dotPassed,
                isCurrent && styles.dotCurrent,
              ]}>
                {isPassed ? (
                  <Icon name="checkmark" size={10} color="#FFFFFF" />
                ) : (
                  <Text style={[styles.dotText, isCurrent && styles.dotTextCurrent]}>
                    {index + 1}
                  </Text>
                )}
              </View>
              {index < dpList.length - 1 && (
                <View style={[styles.line, isPassed && styles.linePassed]} />
              )}
            </View>
            <View style={styles.right}>
              <Text style={[
                styles.label,
                isPassed && styles.labelPassed,
                isCurrent && styles.labelCurrent,
              ]}>
                {dp.guideText}
              </Text>
              {dp.landmarks[0] && (
                <Text style={styles.landmark}>{dp.landmarks[0].name}</Text>
              )}
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingVertical: 8,
  },
  row: {
    flexDirection: 'row',
  },
  left: {
    width: 28,
    alignItems: 'center',
  },
  dot: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: '#EEEEEE',
    justifyContent: 'center',
    alignItems: 'center',
  },
  dotPassed: {
    backgroundColor: '#34C759',
  },
  dotCurrent: {
    backgroundColor: COLORS.primary,
  },
  dotText: {
    fontSize: 11,
    fontWeight: 'bold',
    color: COLORS.subtext,
  },
  dotTextCurrent: {
    color: '#FFFFFF',
  },
  line: {
    width: 2,
    flex: 1,
    backgroundColor: '#EEEEEE',
    minHeight: 20,
  },
  linePassed: {
    backgroundColor: '#34C759',
  },
  right: {
    flex: 1,
    paddingLeft: 10,
    paddingBottom: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: '500',
    color: COLORS.subtext,
  },
  labelPassed: {
    color: '#34C759',
  },
  labelCurrent: {
    color: COLORS.text,
    fontWeight: '600',
  },
  landmark: {
    fontSize: 12,
    color: COLORS.subtext,
    marginTop: 2,
  },
});
