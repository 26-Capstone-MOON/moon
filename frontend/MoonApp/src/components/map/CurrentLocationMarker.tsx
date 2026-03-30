import React from 'react';
import { StyleSheet, View } from 'react-native';
import { NaverMapMarkerOverlay } from '@mj-studio/react-native-naver-map';

interface Props {
  latitude: number;
  longitude: number;
}

export default function CurrentLocationMarker({ latitude, longitude }: Props) {
  return (
    <NaverMapMarkerOverlay
      latitude={latitude}
      longitude={longitude}
      width={24}
      height={24}
      anchor={{ x: 0.5, y: 0.5 }}>
      <View key="current-location" style={styles.outer}>
        <View style={styles.inner} />
      </View>
    </NaverMapMarkerOverlay>
  );
}

const styles = StyleSheet.create({
  outer: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: 'rgba(25, 25, 112, 0.2)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  inner: {
    width: 14,
    height: 14,
    borderRadius: 7,
    backgroundColor: '#191970',
    borderWidth: 2,
    borderColor: '#FFFFFF',
  },
});
