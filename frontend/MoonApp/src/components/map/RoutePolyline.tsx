import React from 'react';
import { NaverMapPathOverlay } from '@mj-studio/react-native-naver-map';
import { COLORS } from '../../constants/colors';
import type { Location } from '../../types/route';

interface Props {
  coordinates: Location[];
  progress?: number;
  color?: string;
  passedColor?: string;
  width?: number;
}

export default function RoutePolyline({
  coordinates,
  progress = 0,
  color = COLORS.primary,
  passedColor = '#B0C4DE',
  width = 5,
}: Props) {
  if (coordinates.length < 2) {
    return null;
  }

  const coords = coordinates.map(c => ({
    latitude: c.latitude,
    longitude: c.longitude,
  }));

  return (
    <NaverMapPathOverlay
      coords={coords}
      width={width}
      color={color}
      passedColor={passedColor}
      progress={progress}
      outlineWidth={1}
      outlineColor="#FFFFFF"
    />
  );
}
