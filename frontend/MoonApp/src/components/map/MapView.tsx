import React from 'react';
import { StyleSheet, type StyleProp, type ViewStyle } from 'react-native';
import { NaverMapView, type NaverMapViewProps } from '@mj-studio/react-native-naver-map';

interface Props extends Omit<NaverMapViewProps, 'style'> {
  style?: StyleProp<ViewStyle>;
  children?: React.ReactNode;
}

export default function MapView({ style, children, ...rest }: Props) {
  return (
    <NaverMapView
      style={[styles.map, style]}
      isShowCompass
      isShowZoomControls
      isShowLocationButton={false}
      {...rest}>
      {children}
    </NaverMapView>
  );
}

const styles = StyleSheet.create({
  map: {
    flex: 1,
  },
});
