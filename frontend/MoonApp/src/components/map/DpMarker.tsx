import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { NaverMapMarkerOverlay } from '@mj-studio/react-native-naver-map';
import Icon from 'react-native-vector-icons/Ionicons';
import { COLORS } from '../../constants/colors';
import type { DecisionPoint } from '../../types/route';

interface Props {
  dp: DecisionPoint;
  index: number;
  isActive?: boolean;
}

function getDpIconName(dpType: string): string {
  switch (dpType) {
    case 'DIRECTION_CHANGE': return 'arrow-forward';
    case 'CROSSWALK': return 'walk-outline';
    case 'VIRTUAL': return 'arrow-up';
    case 'ARRIVAL': return 'flag';
    case 'DEPARTURE': return 'navigate-outline';
    case 'VERTICAL_MOVE': return 'swap-vertical-outline';
    default: return 'ellipse';
  }
}

export default function DpMarker({ dp, index, isActive = false }: Props) {
  const iconName = getDpIconName(dp.dpType);
  const bgColor = isActive ? COLORS.primary : '#FFFFFF';
  const iconColor = isActive ? '#FFFFFF' : COLORS.primary;

  return (
    <NaverMapMarkerOverlay
      latitude={dp.location.latitude}
      longitude={dp.location.longitude}
      width={32}
      height={32}
      caption={dp.landmarks[0] ? { text: dp.landmarks[0].name, textSize: 10, color: COLORS.text } : undefined}>
      <View key={`${dp.dpId}-${isActive}`} style={[styles.marker, { backgroundColor: bgColor }]}>
        <Icon name={iconName} size={16} color={iconColor} />
      </View>
    </NaverMapMarkerOverlay>
  );
}

const styles = StyleSheet.create({
  marker: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: COLORS.primary,
  },
});
