import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Icon from 'react-native-vector-icons/Ionicons';
import type { StackScreenProps } from '@react-navigation/stack';
import { COLORS } from '../constants/colors';
import type { Place, RootStackParamList } from '../types/navigation';

const RECENT_PLACES_KEY = '@moon_recent_places';
const MAX_RECENT = 10;

type Props = StackScreenProps<RootStackParamList, 'Home'>;

export default function HomeScreen({ navigation, route }: Props) {
  const [departure, setDeparture] = useState<Place | null>(null);
  const [destination, setDestination] = useState<Place | null>(null);
  const [recentPlaces, setRecentPlaces] = useState<Place[]>([]);

  // Load recent places from AsyncStorage
  useEffect(() => {
    AsyncStorage.getItem(RECENT_PLACES_KEY).then(json => {
      if (json) {
        setRecentPlaces(JSON.parse(json));
      }
    });
  }, []);

  const addRecentPlace = useCallback(async (place: Place) => {
    const json = await AsyncStorage.getItem(RECENT_PLACES_KEY);
    const current: Place[] = json ? JSON.parse(json) : [];
    const filtered = current.filter(
      p => p.lat !== place.lat || p.lng !== place.lng,
    );
    const updated = [place, ...filtered].slice(0, MAX_RECENT);
    await AsyncStorage.setItem(RECENT_PLACES_KEY, JSON.stringify(updated));
    setRecentPlaces(updated);
  }, []);

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

  const canSearch = departure !== null && destination !== null;

  const handleSearch = () => {
    if (departure && destination) {
      addRecentPlace(destination);
      navigation.navigate('RouteConfirm', { departure, destination });
    }
  };

  const handleSwap = () => {
    setDeparture(destination);
    setDestination(departure);
  };

  const handleReset = () => {
    setDeparture(null);
    setDestination(null);
  };

  const handleRecentPlace = (place: Place) => {
    setDestination(place);
    if (departure) {
      addRecentPlace(place);
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
          <View style={styles.inputArea}>
            <View style={styles.inputFields}>
              <TouchableOpacity
                style={styles.inputRow}
                onPress={() => navigation.navigate('Search', { type: 'departure' })}>
                <Icon name="ellipse" size={8} color={COLORS.primary} style={styles.inputDot} />
                <Text style={departure ? styles.inputTextFilled : styles.inputTextPlaceholder}>
                  {departure ? departure.name : '출발지 입력'}
                </Text>
              </TouchableOpacity>

              <View style={styles.divider} />

              <TouchableOpacity
                style={styles.inputRow}
                onPress={() => navigation.navigate('Search', { type: 'destination' })}>
                <Icon name="ellipse" size={8} color={COLORS.accent} style={styles.inputDot} />
                <Text style={destination ? styles.inputTextFilled : styles.inputTextPlaceholder}>
                  {destination ? destination.name : '도착지 입력'}
                </Text>
              </TouchableOpacity>
            </View>

            <TouchableOpacity style={styles.swapButton} onPress={handleSwap}>
              <Icon name="swap-vertical-outline" size={20} color={COLORS.subtext} />
            </TouchableOpacity>
          </View>

          <View style={styles.cardActions}>
            <TouchableOpacity style={styles.resetButton} onPress={handleReset}>
              <Icon name="refresh-outline" size={16} color={COLORS.subtext} />
              <Text style={styles.resetText}>다시입력</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.searchButton, !canSearch && styles.searchButtonDisabled]}
              onPress={handleSearch}
              disabled={!canSearch}>
              <Text style={[styles.searchButtonText, !canSearch && styles.searchButtonTextDisabled]}>
                길찾기
              </Text>
              <Icon
                name="chevron-forward"
                size={16}
                color={canSearch ? '#FFFFFF' : '#AAAAAA'}
              />
            </TouchableOpacity>
          </View>
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
              <Icon name="alert" size={16} color="#FFFFFF" />
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
                key={`${place.lat}-${place.lng}-${index}`}
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
    paddingBottom: 40,
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
    marginTop: 20,
    elevation: 3,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
  },
  inputArea: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  inputFields: {
    flex: 1,
  },
  inputRow: {
    height: 48,
    flexDirection: 'row',
    alignItems: 'center',
    paddingLeft: 16,
    paddingRight: 8,
  },
  inputDot: {
    marginRight: 10,
  },
  inputTextPlaceholder: {
    fontSize: 15,
    color: '#AAAAAA',
    flex: 1,
  },
  inputTextFilled: {
    fontSize: 15,
    color: '#333333',
    fontWeight: '500',
    flex: 1,
  },
  divider: {
    height: 1,
    backgroundColor: '#EEEEEE',
    marginLeft: 16,
  },
  swapButton: {
    width: 48,
    height: 96,
    justifyContent: 'center',
    alignItems: 'center',
    borderLeftWidth: 1,
    borderLeftColor: '#EEEEEE',
  },
  cardActions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderTopWidth: 1,
    borderTopColor: '#EEEEEE',
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  resetButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  resetText: {
    fontSize: 14,
    color: COLORS.subtext,
  },
  searchButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.primary,
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: 8,
    gap: 2,
  },
  searchButtonDisabled: {
    backgroundColor: '#E5E5E5',
  },
  searchButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: 'bold',
  },
  searchButtonTextDisabled: {
    color: '#AAAAAA',
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
});
