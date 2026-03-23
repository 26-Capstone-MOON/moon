import React, { useEffect, useState } from 'react';
import {
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/Ionicons';
import type { StackScreenProps } from '@react-navigation/stack';
import { COLORS } from '../constants/colors';
import type { Place, RootStackParamList } from '../types/navigation';

type Props = StackScreenProps<RootStackParamList, 'Home'>;

export default function HomeScreen({ navigation, route }: Props) {
  const [departure, setDeparture] = useState<Place | null>(null);
  const [destination, setDestination] = useState<Place | null>(null);
  const [recentPlaces] = useState<Place[]>([]);

  useEffect(() => {
    const params = route.params;
    if (params?.selectedPlace && params?.selectionType) {
      if (params.selectionType === 'departure') {
        setDeparture(params.selectedPlace);
      } else {
        setDestination(params.selectedPlace);
      }
      navigation.setParams({ selectedPlace: undefined, selectionType: undefined });
    }
  }, [route.params, navigation]);

  const canStart = departure !== null && destination !== null;

  const handleStart = () => {
    if (departure && destination) {
      navigation.navigate('RouteConfirm', { departure, destination });
    }
  };

  const handleRecentPlace = (place: Place) => {
    setDestination(place);
    if (departure) {
      navigation.navigate('RouteConfirm', { departure, destination: place });
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}>

        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.logo}>MOON</Text>
          <TouchableOpacity onPress={() => Alert.alert('설정', '추후 구현')}>
            <Icon name="settings-outline" size={24} color={COLORS.text} />
          </TouchableOpacity>
        </View>
        <Text style={styles.greeting}>안녕하세요</Text>
        <Text style={styles.title}>{'어디로\n모실까요?'}</Text>

        {/* Search Card */}
        <View style={styles.searchCard}>
          <TouchableOpacity
            style={styles.searchRow}
            onPress={() => navigation.navigate('Search', { type: 'departure' })}>
            <View style={[styles.dot, { backgroundColor: COLORS.primary }]} />
            <Text style={[styles.searchText, departure && styles.searchTextFilled]}>
              {departure ? departure.name : '현재 위치'}
            </Text>
          </TouchableOpacity>

          <View style={styles.dashedLineContainer}>
            <View style={styles.dashedLine} />
          </View>

          <TouchableOpacity
            style={styles.searchRow}
            onPress={() => navigation.navigate('Search', { type: 'destination' })}>
            <View style={[styles.dot, { backgroundColor: '#FF4444' }]} />
            <View style={styles.destinationRow}>
              <Text
                style={[
                  styles.searchText,
                  !destination && styles.placeholder,
                  destination && styles.searchTextFilled,
                ]}>
                {destination ? destination.name : '도착지를 입력하세요'}
              </Text>
              {destination ? (
                <TouchableOpacity
                  onPress={(e) => {
                    e.stopPropagation();
                    setDestination(null);
                  }}
                  hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
                  <Icon name="close-circle-outline" size={20} color="#AAAAAA" />
                </TouchableOpacity>
              ) : (
                <Icon name="mic-outline" size={20} color="#AAAAAA" />
              )}
            </View>
          </TouchableOpacity>
        </View>

        {/* Shortcut Cards */}
        <View style={styles.shortcutRow}>
          <TouchableOpacity
            style={[styles.shortcutCard, { backgroundColor: '#EFF6FF' }]}
            onPress={() => Alert.alert('바로가기', '추후 구현')}>
            <Icon name="home-outline" size={24} color={COLORS.primary} />
            <Text style={styles.shortcutLabel}>바로가기</Text>
            <Text style={styles.shortcutTitle}>우리집</Text>
            <Text style={styles.shortcutSub}>장소를 등록해주세요</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.shortcutCard, { backgroundColor: '#FFF0EB' }]}
            onPress={() => Alert.alert('길을 잃었다면', '추후 구현')}>
            <View style={styles.alertIcon}>
              <Icon name="warning" size={16} color="#FFFFFF" />
            </View>
            <Text style={styles.shortcutLabel}>길을 잃었다면</Text>
            <Text style={styles.shortcutTitle}>잃어버렸어요</Text>
          </TouchableOpacity>
        </View>

        {/* Recent Places */}
        <View style={styles.recentSection}>
          <View style={styles.recentHeader}>
            <Icon name="time-outline" size={18} color={COLORS.text} />
            <Text style={styles.recentTitle}>최근에 간 곳</Text>
          </View>

          {recentPlaces.length === 0 ? (
            <Text style={styles.emptyText}>최근 방문 기록이 없습니다</Text>
          ) : (
            recentPlaces.map((place, index) => (
              <TouchableOpacity
                key={`${place.name}-${index}`}
                style={[
                  styles.recentItem,
                  index < recentPlaces.length - 1 && styles.recentItemBorder,
                ]}
                onPress={() => handleRecentPlace(place)}>
                <Icon name="location-outline" size={20} color={COLORS.subtext} />
                <View style={styles.recentInfo}>
                  <Text style={styles.recentName}>{place.name}</Text>
                  <Text style={styles.recentAddress}>
                    {place.address}
                    {place.distance ? ` · ${place.distance}` : ''}
                  </Text>
                </View>
              </TouchableOpacity>
            ))
          )}
        </View>
      </ScrollView>

      {/* Start Button */}
      {canStart && (
        <View style={styles.startButtonContainer}>
          <TouchableOpacity style={styles.startButton} onPress={handleStart}>
            <Text style={styles.startButtonText}>네, 안내를 시작할까요?</Text>
          </TouchableOpacity>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingBottom: 100,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 16,
  },
  logo: {
    fontSize: 20,
    fontWeight: 'bold',
    color: COLORS.primary,
  },
  greeting: {
    fontSize: 14,
    color: COLORS.subtext,
    marginTop: 24,
  },
  title: {
    fontSize: 26,
    fontWeight: 'bold',
    color: COLORS.text,
    lineHeight: 36,
    marginTop: 4,
  },

  // Search Card
  searchCard: {
    backgroundColor: COLORS.background,
    borderRadius: 16,
    paddingHorizontal: 16,
    paddingVertical: 14,
    marginTop: 20,
    elevation: 3,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
  },
  searchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 12,
  },
  searchText: {
    fontSize: 14,
    color: COLORS.text,
    flex: 1,
  },
  searchTextFilled: {
    color: COLORS.text,
    fontWeight: '500',
  },
  placeholder: {
    color: '#AAAAAA',
  },
  destinationRow: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  dashedLineContainer: {
    paddingLeft: 3,
    height: 16,
    justifyContent: 'center',
  },
  dashedLine: {
    width: 0,
    height: 16,
    borderLeftWidth: 1.5,
    borderStyle: 'dashed',
    borderColor: '#CCCCCC',
  },

  // Shortcut Cards
  shortcutRow: {
    flexDirection: 'row',
    marginTop: 20,
    gap: 12,
  },
  shortcutCard: {
    flex: 1,
    borderRadius: 16,
    padding: 16,
  },
  shortcutLabel: {
    fontSize: 12,
    color: COLORS.subtext,
    marginTop: 10,
  },
  shortcutTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: COLORS.text,
    marginTop: 2,
  },
  shortcutSub: {
    fontSize: 11,
    color: '#AAAAAA',
    marginTop: 4,
  },
  alertIcon: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#FF6B35',
    justifyContent: 'center',
    alignItems: 'center',
  },

  // Recent Places
  recentSection: {
    marginTop: 28,
  },
  recentHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  recentTitle: {
    fontSize: 15,
    fontWeight: 'bold',
    color: COLORS.text,
  },
  emptyText: {
    fontSize: 14,
    color: '#AAAAAA',
    textAlign: 'center',
    paddingVertical: 40,
  },
  recentItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    gap: 12,
  },
  recentItemBorder: {
    borderBottomWidth: 0.5,
    borderBottomColor: '#EEEEEE',
  },
  recentInfo: {
    flex: 1,
  },
  recentName: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.text,
  },
  recentAddress: {
    fontSize: 12,
    color: COLORS.subtext,
    marginTop: 2,
  },

  // Start Button
  startButtonContainer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    paddingHorizontal: 20,
    paddingBottom: 24,
    backgroundColor: COLORS.background,
  },
  startButton: {
    backgroundColor: COLORS.primary,
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
  },
  startButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
});
