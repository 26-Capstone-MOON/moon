import React from 'react';
import { StyleSheet, TouchableOpacity } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import { COLORS } from '../../constants/colors';

interface Props {
  onPress: () => void;
  isListening?: boolean;
  size?: number;
}

export default function VoiceButton({ onPress, isListening = false, size = 56 }: Props) {
  return (
    <TouchableOpacity
      style={[
        styles.button,
        {
          width: size,
          height: size,
          borderRadius: size / 2,
          backgroundColor: isListening ? COLORS.accent : COLORS.primary,
        },
      ]}
      onPress={onPress}
      activeOpacity={0.7}>
      <Icon
        name={isListening ? 'mic' : 'mic-outline'}
        size={size * 0.45}
        color="#FFFFFF"
      />
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  button: {
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.15,
    shadowRadius: 6,
  },
});
