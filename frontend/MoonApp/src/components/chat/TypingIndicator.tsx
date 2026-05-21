import React, { useEffect, useRef } from 'react';
import { Animated, Easing, StyleSheet, View } from 'react-native';
import { COLORS } from '../../constants/colors';

const DOT_SIZE = 8;
const DOT_GAP = 4;
const CYCLE_MS = 600;
const STAGGER_MS = 200;
const JUMP_PX = 5;

function useDotAnim(delay: number) {
  const v = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(v, {
          toValue: -JUMP_PX,
          duration: CYCLE_MS / 3,
          easing: Easing.out(Easing.quad),
          useNativeDriver: true,
        }),
        Animated.timing(v, {
          toValue: 0,
          duration: CYCLE_MS / 3,
          easing: Easing.in(Easing.quad),
          useNativeDriver: true,
        }),
        Animated.delay(CYCLE_MS / 3),
      ]),
    );
    const startTimer = setTimeout(() => loop.start(), delay);
    return () => {
      clearTimeout(startTimer);
      loop.stop();
    };
  }, [v, delay]);
  return v;
}

export default function TypingIndicator() {
  const d1 = useDotAnim(0);
  const d2 = useDotAnim(STAGGER_MS);
  const d3 = useDotAnim(STAGGER_MS * 2);

  return (
    <View style={styles.row}>
      <View style={styles.bubble}>
        <View style={styles.dotsRow}>
          <Animated.View style={[styles.dot, { transform: [{ translateY: d1 }] }]} />
          <Animated.View style={[styles.dot, { transform: [{ translateY: d2 }] }]} />
          <Animated.View style={[styles.dot, { transform: [{ translateY: d3 }] }]} />
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    marginVertical: 4,
  },
  bubble: {
    maxWidth: '82%',
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 12,
    borderTopLeftRadius: 4,
    backgroundColor: '#FFFFFF',
    borderWidth: 0.5,
    borderColor: '#E5E5EA',
  },
  dotsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    height: DOT_SIZE + JUMP_PX,
    paddingHorizontal: 2,
  },
  dot: {
    width: DOT_SIZE,
    height: DOT_SIZE,
    borderRadius: DOT_SIZE / 2,
    backgroundColor: COLORS.primary,
    marginHorizontal: DOT_GAP / 2,
  },
});
