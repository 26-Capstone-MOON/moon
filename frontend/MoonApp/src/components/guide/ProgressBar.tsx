import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { COLORS } from '../../constants/colors';

interface Props {
  current: number;
  total: number;
}

export default function ProgressBar({ current, total }: Props) {
  const progress = total > 0 ? (current / total) * 100 : 0;

  return (
    <View style={styles.container}>
      <View style={styles.barBg}>
        <View style={[styles.barFill, { width: `${progress}%` }]} />
      </View>
      <Text style={styles.label}>{Math.round(progress)}%</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  barBg: {
    flex: 1,
    height: 4,
    backgroundColor: '#EEEEEE',
    borderRadius: 2,
  },
  barFill: {
    height: 4,
    backgroundColor: COLORS.primary,
    borderRadius: 2,
  },
  label: {
    fontSize: 13,
    fontWeight: '600',
    color: COLORS.primary,
    minWidth: 36,
    textAlign: 'right',
  },
});
