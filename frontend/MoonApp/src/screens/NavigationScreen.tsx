import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import type { StackScreenProps } from '@react-navigation/stack';
import { COLORS } from '../constants/colors';
import type { RootStackParamList } from '../types/navigation';

type Props = StackScreenProps<RootStackParamList, 'Navigation'>;

export default function NavigationScreen({ route }: Props) {
  const { destination } = route.params;

  return (
    <View style={styles.container}>
      <Text style={styles.text}>실시간 안내</Text>
      <Text style={styles.sub}>{destination.name}</Text>
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
  sub: {
    fontSize: 16,
    color: COLORS.subtext,
    marginTop: 8,
  },
});
