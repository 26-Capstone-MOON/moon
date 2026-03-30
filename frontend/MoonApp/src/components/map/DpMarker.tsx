import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { NaverMapMarkerOverlay } from '@mj-studio/react-native-naver-map';
import { COLORS } from '../../constants/colors';
import type { DecisionPoint } from '../../types/route';

interface Props {
  dp: DecisionPoint;
  index: number;
  isActive?: boolean;
}

export default function DpMarker({ dp, index, isActive = false }: Props) {
  const bgColor = isActive ? COLORS.primary : '#FFFFFF';
  const textColor = isActive ? '#FFFFFF' : COLORS.primary;

  return (
    <NaverMapMarkerOverlay
      latitude={dp.location.latitude}
      longitude={dp.location.longitude}
      width={24}
      height={24}
      caption={dp.landmarks[0] ? { text: dp.landmarks[0].name, textSize: 10, color: COLORS.text } : undefined}>
      <View key={`${dp.dpId}-${isActive}`} style={[styles.marker, { backgroundColor: bgColor }]}>
        <Text style={[styles.markerText, { color: textColor }]}>{index + 1}</Text>
      </View>
    </NaverMapMarkerOverlay>
  );
}

const styles = StyleSheet.create({
  marker: {
    width: 24,
    height: 24,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1.5,
    borderColor: COLORS.primary,
  },
  markerText: {
    fontSize: 11,
    fontWeight: 'bold',
  },
});
