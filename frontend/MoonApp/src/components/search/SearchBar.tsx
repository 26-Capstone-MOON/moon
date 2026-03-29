import React from 'react';
import { StyleSheet, TextInput, TouchableOpacity, View } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import { COLORS } from '../../constants/colors';

interface Props {
  value: string;
  onChangeText: (text: string) => void;
  onSubmit?: () => void;
  onClear?: () => void;
  onMicPress?: () => void;
  isMicActive?: boolean;
  placeholder?: string;
  autoFocus?: boolean;
}

export default function SearchBar({
  value,
  onChangeText,
  onSubmit,
  onClear,
  onMicPress,
  isMicActive = false,
  placeholder = '장소를 검색하세요',
  autoFocus = false,
}: Props) {
  return (
    <View style={styles.container}>
      <Icon name="search" size={18} color={COLORS.subtext} style={styles.icon} />
      <TextInput
        style={styles.input}
        value={value}
        onChangeText={onChangeText}
        onSubmitEditing={onSubmit}
        placeholder={placeholder}
        placeholderTextColor="#BBBBBB"
        autoFocus={autoFocus}
        returnKeyType="search"
      />
      {value.length > 0 && (
        <TouchableOpacity
          onPress={onClear}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          style={styles.clearBtn}>
          <Icon name="close-circle" size={18} color="#CCCCCC" />
        </TouchableOpacity>
      )}
      {onMicPress && (
        <TouchableOpacity
          onPress={onMicPress}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          style={styles.micBtn}>
          <Icon
            name={isMicActive ? 'mic' : 'mic-outline'}
            size={20}
            color={isMicActive ? COLORS.accent : COLORS.subtext}
          />
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F2F3F5',
    borderRadius: 10,
    paddingHorizontal: 12,
    height: 44,
  },
  icon: {
    marginRight: 8,
  },
  input: {
    flex: 1,
    fontSize: 15,
    color: COLORS.text,
    padding: 0,
  },
  clearBtn: {
    marginLeft: 4,
  },
  micBtn: {
    marginLeft: 8,
    padding: 2,
  },
});
