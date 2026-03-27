import React, { useEffect } from 'react';
import { Animated, StyleSheet, Text } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';

interface Props {
  message: string;
  visible: boolean;
  onDismiss: () => void;
  duration?: number;
}

export default function ErrorToast({ message, visible, onDismiss, duration = 3000 }: Props) {
  const opacity = React.useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (visible) {
      Animated.timing(opacity, { toValue: 1, duration: 200, useNativeDriver: true }).start();
      const timer = setTimeout(() => {
        Animated.timing(opacity, { toValue: 0, duration: 200, useNativeDriver: true }).start(onDismiss);
      }, duration);
      return () => clearTimeout(timer);
    }
  }, [visible, duration, onDismiss, opacity]);

  if (!visible) {
    return null;
  }

  return (
    <Animated.View style={[styles.container, { opacity }]}>
      <Icon name="alert-circle-outline" size={18} color="#FFFFFF" />
      <Text style={styles.text}>{message}</Text>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    bottom: 80,
    left: 20,
    right: 20,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#333333',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 10,
    elevation: 5,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 6,
    zIndex: 200,
  },
  text: {
    flex: 1,
    fontSize: 14,
    color: '#FFFFFF',
  },
});
