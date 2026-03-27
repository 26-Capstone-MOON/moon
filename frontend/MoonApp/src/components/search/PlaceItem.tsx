import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';
import { COLORS } from '../../constants/colors';

interface Props {
  name: string;
  address: string;
  category?: string;
  distance?: string;
  onPress: () => void;
}

export default function PlaceItem({ name, address, category, distance, onPress }: Props) {
  return (
    <TouchableOpacity style={styles.container} onPress={onPress} activeOpacity={0.6}>
      <View style={styles.iconContainer}>
        <Icon name="location-outline" size={20} color={COLORS.primary} />
      </View>
      <View style={styles.content}>
        <View style={styles.nameRow}>
          <Text style={styles.name} numberOfLines={1}>{name}</Text>
          {category && <Text style={styles.category}>{category}</Text>}
        </View>
        <Text style={styles.address} numberOfLines={1}>{address}</Text>
      </View>
      {distance && <Text style={styles.distance}>{distance}</Text>}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  iconContainer: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#F0F4FF',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  content: {
    flex: 1,
  },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  name: {
    fontSize: 15,
    fontWeight: '600',
    color: COLORS.text,
  },
  category: {
    fontSize: 11,
    color: COLORS.subtext,
    backgroundColor: '#F0F0F0',
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 4,
  },
  address: {
    fontSize: 13,
    color: COLORS.subtext,
    marginTop: 2,
  },
  distance: {
    fontSize: 12,
    color: COLORS.primary,
    fontWeight: '500',
    marginLeft: 8,
  },
});
