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
          <TouchableOpacity
            style={styles.settingsBtn}
            onPress={() => Alert.alert('설정', '추후 구현')}>
            <Icon name="settings-outline" size={20} color={COLORS.primary} />
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
                <View style={styles.dotDeparture} />
                <Text style={departure ? styles.inputTextFilled : styles.inputTextPlaceholder}>
                  {departure ? departure.name : '출발지 입력'}
                </Text>
              </TouchableOpacity>

              <View style={styles.divider} />

              <TouchableOpacity
                style={styles.inputRow}
                onPress={() => navigation.navigate('Search', { type: 'destination' })}>
                <View style={styles.dotDestination} />
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
                color={canSearch ? '#FFFFFF' : COLORS.primary}
              />
            </TouchableOpacity>
          </View>
        </View>

        {/* Shortcut Cards */}
        <View style={styles.shortcutRow}>
          <TouchableOpacity
            style={styles.shortcutCard}
            activeOpacity={0.7}
            onPress={() => Alert.alert('바로가기', '추후 구현')}>
            <View style={styles.shortcutIconWrapHome}>
              <Icon name="home-outline" size={20} color={COLORS.primary} />
            </View>
            <View style={styles.shortcutSpacer} />
            <Text style={styles.shortcutLabel}>바로가기</Text>
            <Text style={styles.shortcutTitle}>우리집</Text>
            <Text style={styles.shortcutSub}>장소를 등록해주세요</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.shortcutCard}
            activeOpacity={0.7}
            onPress={() => Alert.alert('길을 잃었다면', '추후 구현')}>
            <View style={styles.shortcutIconWrapAlert}>
              <Icon name="alert" size={20} color="#E85030" />
            </View>
            <View style={styles.shortcutSpacer} />
            <Text style={styles.shortcutLabel}>길을 잃었다면</Text>
            <Text style={styles.shortcutTitleAlert}>잃어버렸어요</Text>
          </TouchableOpacity>
        </View>

        {/* Recent Places */}
        <View style={styles.recentSection}>
          <View style={styles.recentHeader}>
            <Icon name="time-outline" size={18} color={COLORS.primary} />
            <Text style={styles.recentTitle}>최근에 간 곳</Text>
          </View>

          {recentPlaces.length === 0 ? (
            <View style={styles.emptyCard}>
              <View style={styles.emptyIconWrap}>
                <Icon name="location-outline" size={24} color={COLORS.subtext} />
              </View>
              <Text style={styles.emptyText}>최근 방문 기록이 없습니다</Text>
              <Text style={styles.emptySub}>길안내를 시작해보세요</Text>
            </View>
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

const CARD_SHADOW = {
  shadowColor: '#000',
  shadowOffset: { width: 0, height: 2 },
  shadowOpacity: 0.08,
  shadowRadius: 12,
  elevation: 3,
} as const;

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

  // Header
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 16,
  },
  logo: {
    fontSize: 22,
    fontWeight: 'bold',
    fontFamily: 'SourGummy-Bold',
    color: COLORS.primary,
  },
  settingsBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#EDEAE7',
    justifyContent: 'center',
    alignItems: 'center',
  },
  greeting: {
    fontSize: 13,
    color: '#888888',
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
    backgroundColor: COLORS.card,
    borderRadius: 16,
    marginTop: 20,
    marginBottom: 16,
    ...CARD_SHADOW,
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
  dotDeparture: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: COLORS.primary,
    marginRight: 10,
  },
  dotDestination: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: 'rgba(25, 25, 112, 0.4)',
    marginRight: 10,
  },
  inputTextPlaceholder: {
    fontSize: 15,
    color: '#AAAAAA',
    flex: 1,
  },
  inputTextFilled: {
    fontSize: 15,
    color: COLORS.text,
    fontWeight: '500',
    flex: 1,
  },
  divider: {
    height: 1,
    backgroundColor: '#EEEBE8',
    marginLeft: 16,
  },
  swapButton: {
    width: 48,
    height: 96,
    justifyContent: 'center',
    alignItems: 'center',
    borderLeftWidth: 1,
    borderLeftColor: '#EEEBE8',
  },
  cardActions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderTopWidth: 1,
    borderTopColor: '#EEEBE8',
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
    paddingHorizontal: 20,
    paddingVertical: 8,
    borderRadius: 8,
    gap: 2,
  },
  searchButtonDisabled: {
    backgroundColor: 'rgba(25, 25, 112, 0.1)',
  },
  searchButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: 'bold',
  },
  searchButtonTextDisabled: {
    color: COLORS.primary,
  },

  // Shortcut Cards
  shortcutRow: {
    flexDirection: 'row',
    alignItems: 'stretch',
    gap: 12,
    marginBottom: 16,
  },
  shortcutCard: {
    flex: 1,
    backgroundColor: COLORS.card,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#E8E8E8',
    padding: 20,
  },
  shortcutSpacer: {
    flex: 1,
  },
  shortcutIconWrapHome: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: '#EEEEF8',
    justifyContent: 'center',
    alignItems: 'center',
  },
  shortcutIconWrapAlert: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: '#FFF0ED',
    justifyContent: 'center',
    alignItems: 'center',
  },
  shortcutLabel: {
    fontSize: 11,
    color: COLORS.subtext,
    marginTop: 0,
  },
  shortcutTitle: {
    fontSize: 17,
    fontWeight: 'bold',
    color: COLORS.primary,
    marginTop: 2,
  },
  shortcutTitleAlert: {
    fontSize: 17,
    fontWeight: 'bold',
    color: '#8B2500',
    marginTop: 2,
  },
  shortcutSub: {
    fontSize: 11,
    color: '#BBBBBB',
    marginTop: 4,
  },

  // Recent Places
  recentSection: {
    marginTop: 12,
  },
  recentHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  recentTitle: {
    fontSize: 15,
    fontWeight: 'bold',
    color: COLORS.primary,
  },
  emptyCard: {
    backgroundColor: COLORS.card,
    borderRadius: 14,
    marginTop: 12,
    paddingVertical: 36,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 10,
    elevation: 2,
  },
  emptyIconWrap: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#F0EDEA',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  emptyText: {
    fontSize: 14,
    fontWeight: '500',
    color: COLORS.subtext,
  },
  emptySub: {
    fontSize: 12,
    color: '#BBBBBB',
    marginTop: 4,
  },
  recentItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    gap: 12,
  },
  recentItemBorder: {
    borderBottomWidth: 0.5,
    borderBottomColor: COLORS.cardBorder,
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
