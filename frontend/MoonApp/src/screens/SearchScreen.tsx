import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  FlatList,
  Keyboard,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/Ionicons';
import type { StackScreenProps } from '@react-navigation/stack';
import { COLORS } from '../constants/colors';
import { searchPlaces } from '../services/searchService';
import { useSTT } from '../hooks/useSTT';
import PlaceItem from '../components/search/PlaceItem';
import LoadingOverlay from '../components/common/LoadingOverlay';
import { formatDistance } from '../utils/formatDistance';
import type { RootStackParamList, SearchResult, Place } from '../types/navigation';

type Props = StackScreenProps<RootStackParamList, 'Search'>;

function haversineMeters(
  lat1: number, lng1: number,
  lat2: number, lng2: number,
): number {
  const toRad = (v: number) => (v * Math.PI) / 180;
  const R = 6371000;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

const DEFAULT_ORIGIN: Place = {
  name: '현재 위치',
  address: '서울특별시 중구 세종대로 110',
  lat: 37.5665,
  lng: 126.978,
};

export default function SearchScreen({ navigation, route }: Props) {
  const { type } = route.params;

  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [selectedPlace, setSelectedPlace] = useState<Place | null>(null);

  const { transcript, isListening, startListening, stopListening } = useSTT();
  const inputRef = useRef<TextInput>(null);

  const isDeparture = type === 'departure';
  const title = isDeparture ? '출발지 검색' : '도착지 검색';
  const placeholder = isDeparture ? '출발지를 입력하세요' : '도착지를 입력하세요';
  const dotColor = isDeparture ? COLORS.primary : COLORS.accent;

  // STT transcript -> query
  useEffect(() => {
    if (transcript.length > 0) {
      setQuery(transcript);
    }
  }, [transcript]);

  // Debounced search
  const doSearch = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (trimmed.length < 1) {
      setResults([]);
      setSearched(false);
      return;
    }
    setLoading(true);
    try {
      const data = await searchPlaces(trimmed);
      setResults(data);
    } catch (e) {
      console.warn('Search error:', e);
      setResults([]);
    } finally {
      setLoading(false);
      setSearched(true);
    }
  }, []);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      setSearched(false);
      return;
    }
    if (timerRef.current) { clearTimeout(timerRef.current); }
    timerRef.current = setTimeout(() => { doSearch(query); }, 800);
    return () => {
      if (timerRef.current) { clearTimeout(timerRef.current); }
    };
  }, [query, doSearch]);

  const handleSubmit = () => {
    if (timerRef.current) { clearTimeout(timerRef.current); }
    doSearch(query);
  };

  const handleMicPress = () => {
    if (isListening) { stopListening(); }
    else { startListening(); }
  };

  const handleSelect = (item: SearchResult) => {
    Keyboard.dismiss();
    setSelectedPlace({
      name: item.name,
      address: item.address,
      category: item.category,
      lat: item.lat,
      lng: item.lng,
    });
  };

  const handleConfirm = () => {
    if (!selectedPlace) { return; }

    if (isDeparture) {
      navigation.navigate('Home', {
        selectedPlace,
        selectionType: 'departure',
      });
    } else {
      navigation.navigate('RouteConfirm', {
        departure: DEFAULT_ORIGIN,
        destination: selectedPlace,
      });
    }
  };

  const handleDismiss = () => {
    setSelectedPlace(null);
  };

  const renderItem = ({ item }: { item: SearchResult }) => (
    <PlaceItem
      name={item.name}
      address={item.address}
      category={item.category}
      onPress={() => handleSelect(item)}
    />
  );

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      {isListening ? (
        <>
          <Icon name="mic" size={32} color={COLORS.accent} />
          <Text style={styles.listeningText}>듣고 있어요...</Text>
        </>
      ) : (
        <Text style={styles.emptyText}>
          {searched ? '검색 결과가 없습니다' : '장소를 검색해보세요'}
        </Text>
      )}
    </View>
  );

  const renderSeparator = () => <View style={styles.separator} />;

  return (
    <SafeAreaView style={styles.safe}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity
          onPress={() => navigation.goBack()}
          style={styles.backBtn}
          hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Icon name="arrow-back" size={22} color={COLORS.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{title}</Text>
      </View>

      {/* Single input field */}
      <View style={styles.inputContainer}>
        <Icon name="ellipse" size={8} color={dotColor} style={styles.fieldDot} />
        <TextInput
          ref={inputRef}
          style={styles.fieldInput}
          value={query}
          onChangeText={setQuery}
          onSubmitEditing={handleSubmit}
          placeholder={placeholder}
          placeholderTextColor="#BBBBBB"
          returnKeyType="search"
          autoFocus
        />
        {query.length > 0 && (
          <TouchableOpacity
            onPress={() => { setQuery(''); setResults([]); setSearched(false); }}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
            <Icon name="close-circle" size={16} color="#CCCCCC" />
          </TouchableOpacity>
        )}
        <TouchableOpacity
          onPress={handleMicPress}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          style={styles.micBtn}>
          <Icon
            name={isListening ? 'mic' : 'mic-outline'}
            size={18}
            color={isListening ? COLORS.accent : COLORS.subtext}
          />
        </TouchableOpacity>
      </View>

      {loading && <LoadingOverlay message="장소를 검색하고 있어요..." />}

      <FlatList
        data={results}
        keyExtractor={(item, index) => `${item.name}-${item.lat}-${index}`}
        renderItem={renderItem}
        ListEmptyComponent={!loading ? renderEmpty : null}
        ItemSeparatorComponent={renderSeparator}
        keyboardShouldPersistTaps="handled"
      />

      {/* Confirm Modal */}
      <Modal
        visible={selectedPlace !== null}
        transparent
        animationType="slide"
        onRequestClose={handleDismiss}>
        <Pressable style={styles.modalOverlay} onPress={handleDismiss}>
          <Pressable style={styles.modalSheet} onPress={() => {}}>
            <View style={styles.modalHandle} />

            <Text style={styles.modalQuestion}>
              이 주소로 안내를 시작할까요?
            </Text>

            <View style={styles.modalPlaceInfo}>
              <Icon name="location" size={20} color={COLORS.primary} />
              <View style={styles.modalPlaceText}>
                <Text style={styles.modalPlaceName}>{selectedPlace?.name}</Text>
                <View style={styles.modalMeta}>
                  {selectedPlace?.category ? (
                    <View style={styles.categoryTag}>
                      <Text style={styles.categoryTagText}>{selectedPlace.category}</Text>
                    </View>
                  ) : null}
                  {selectedPlace ? (
                    <Text style={styles.distanceText}>
                      {formatDistance(haversineMeters(
                        DEFAULT_ORIGIN.lat, DEFAULT_ORIGIN.lng,
                        selectedPlace.lat, selectedPlace.lng,
                      ))}
                    </Text>
                  ) : null}
                </View>
                <Text style={styles.modalPlaceAddr}>{selectedPlace?.address}</Text>
              </View>
            </View>

            <TouchableOpacity
              style={styles.confirmBtn}
              activeOpacity={0.8}
              onPress={handleConfirm}>
              <Text style={styles.confirmBtnText}>
                {isDeparture ? '출발지로 선택' : '네, 안내 시작'}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.dismissBtn}
              activeOpacity={0.6}
              onPress={handleDismiss}>
              <Text style={styles.dismissBtnText}>다시 검색</Text>
            </TouchableOpacity>
          </Pressable>
        </Pressable>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingLeft: 12,
    paddingRight: 16,
    paddingVertical: 12,
  },
  backBtn: {
    width: 32,
    height: 32,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 8,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: 'bold',
    color: COLORS.text,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 16,
    marginBottom: 8,
    backgroundColor: '#F2F3F5',
    borderRadius: 12,
    paddingHorizontal: 14,
    height: 48,
  },
  fieldDot: {
    marginRight: 10,
  },
  fieldInput: {
    flex: 1,
    fontSize: 15,
    color: COLORS.text,
    fontWeight: '500',
    padding: 0,
  },
  micBtn: {
    marginLeft: 6,
    padding: 2,
  },
  separator: {
    height: 0.5,
    backgroundColor: '#EEEEEE',
    marginLeft: 56,
  },
  emptyContainer: {
    justifyContent: 'center',
    alignItems: 'center',
    paddingTop: 80,
    gap: 8,
  },
  emptyText: {
    fontSize: 14,
    color: '#AAAAAA',
  },
  listeningText: {
    fontSize: 14,
    color: COLORS.accent,
    fontWeight: '500',
  },

  // Modal
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.35)',
    justifyContent: 'flex-end',
  },
  modalSheet: {
    backgroundColor: COLORS.background,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 24,
    paddingBottom: 36,
    paddingTop: 12,
  },
  modalHandle: {
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: '#DDDDDD',
    alignSelf: 'center',
    marginBottom: 20,
  },
  modalQuestion: {
    fontSize: 18,
    fontWeight: 'bold',
    color: COLORS.text,
    textAlign: 'center',
    marginBottom: 20,
  },
  modalPlaceInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F7F8FA',
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
    gap: 12,
  },
  modalPlaceText: {
    flex: 1,
  },
  modalPlaceName: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.text,
  },
  modalMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 4,
  },
  categoryTag: {
    backgroundColor: '#EBF2FC',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  categoryTagText: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.primary,
  },
  distanceText: {
    fontSize: 12,
    color: COLORS.subtext,
  },
  modalPlaceAddr: {
    fontSize: 13,
    color: COLORS.subtext,
    marginTop: 4,
  },
  confirmBtn: {
    backgroundColor: COLORS.primary,
    borderRadius: 14,
    height: 52,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 10,
  },
  confirmBtnText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
  dismissBtn: {
    height: 44,
    justifyContent: 'center',
    alignItems: 'center',
  },
  dismissBtnText: {
    color: COLORS.subtext,
    fontSize: 14,
  },
});
