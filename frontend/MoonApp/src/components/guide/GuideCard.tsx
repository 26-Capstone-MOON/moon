import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import { COLORS } from '../../constants/colors';

interface Props {
  dpType: string;
  guideText: string;
  landmarkName?: string;
  nextGuideText?: string;
}

function getDirectionIcon(dpType: string): string {
  switch (dpType) {
    case 'DIRECTION_CHANGE': return 'arrow-forward';
    case 'CROSSWALK': return 'walk-outline';
    case 'VIRTUAL': return 'arrow-up';
    case 'ARRIVAL': return 'flag';
    case 'DEPARTURE': return 'navigate-outline';
    case 'VERTICAL_MOVE': return 'swap-vertical-outline';
    default: return 'navigate-outline';
  }
}

export default function GuideCard({ dpType, guideText, landmarkName, nextGuideText }: Props) {
  return (
    <View style={styles.card}>
      <View style={styles.iconContainer}>
        <Icon name={getDirectionIcon(dpType)} size={28} color={COLORS.primary} />
      </View>
      <View style={styles.content}>
        {landmarkName && (
          <View style={styles.landmarkRow}>
            <Icon name="pin-outline" size={12} color={COLORS.primary} />
            <Text style={styles.landmarkText}>{landmarkName}</Text>
          </View>
        )}
        <Text style={styles.guideText}>{guideText}</Text>
        {nextGuideText && (
          <Text style={styles.nextHint}>다음: {nextGuideText}</Text>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    backgroundColor: COLORS.background,
    borderRadius: 16,
    elevation: 3,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
  },
  iconContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#F0F4FF',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  content: {
    flex: 1,
  },
  landmarkRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginBottom: 4,
  },
  landmarkText: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.primary,
  },
  guideText: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.text,
    lineHeight: 22,
  },
  nextHint: {
    fontSize: 12,
    color: COLORS.subtext,
    marginTop: 6,
  },
});
