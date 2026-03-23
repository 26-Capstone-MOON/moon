import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { COLORS } from '../constants/colors';

export default function ProgressScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.text}>경로 진행 상황</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: COLORS.background,
  },
  text: {
    fontSize: 24,
    color: COLORS.text,
  },
});
