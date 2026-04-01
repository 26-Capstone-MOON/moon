import React, { useEffect, useRef } from 'react';
import { Animated, StyleSheet, Text, View } from 'react-native';

interface Props {
  visible: boolean;
}

export default function DeviationBanner({ visible }: Props) {
  const opacity = useRef(new Animated.Value(0)).current;
  const loopRef = useRef<Animated.CompositeAnimation | null>(null);

  useEffect(() => {
    if (visible) {
      const loop = Animated.loop(
        Animated.sequence([
          Animated.timing(opacity, {
            toValue: 1,
            duration: 750,
            useNativeDriver: true,
          }),
          Animated.timing(opacity, {
            toValue: 0,
            duration: 750,
            useNativeDriver: true,
          }),
        ]),
      );
      loopRef.current = loop;
      loop.start();
    } else {
      loopRef.current?.stop();
      opacity.setValue(0);
    }

    return () => {
      loopRef.current?.stop();
    };
  }, [visible, opacity]);

  if (!visible) { return null; }

  return (
    <View style={styles.container} pointerEvents="none">
      {/* Pulsing red overlay */}
      <Animated.View style={[styles.overlay, { opacity }]} />

      {/* Warning text at top center */}
      <View style={styles.textWrap}>
        <Text style={styles.text}>경로를 벗어난 것 같아요</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 100,
  },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(255, 50, 50, 0.25)',
  },
  textWrap: {
    position: 'absolute',
    top: 48,
    alignSelf: 'center',
    backgroundColor: 'rgba(211, 47, 47, 0.85)',
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 24,
  },
  text: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '700',
  },
});
