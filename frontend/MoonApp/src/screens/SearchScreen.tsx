import React, { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
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
import type { RootStackParamList, SearchResult } from '../types/navigation';

type Props = StackScreenProps<RootStackParamList, 'Search'>;

export default function SearchScreen({ navigation, route }: Props) {
  const { type } = route.params;
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const inputRef = useRef<TextInput>(null);

  // Manual focus after mount (autoFocus breaks Korean IME on Android)
  const handleLayout = () => {
    setTimeout(() => inputRef.current?.focus(), 100);
  };

  const doSearch = async (text: string) => {
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
  };

  // Auto-search as user types (800ms debounce for Korean IME)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      setSearched(false);
      return;
    }
    if (timerRef.current) { clearTimeout(timerRef.current); }
    timerRef.current = setTimeout(() => {
      doSearch(query);
    }, 800);
    return () => {
      if (timerRef.current) { clearTimeout(timerRef.current); }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  const handleSubmit = () => {
    if (timerRef.current) { clearTimeout(timerRef.current); }
    doSearch(query);
  };

  const handleSelect = (item: SearchResult) => {
    navigation.navigate('Home', {
      selectedPlace: {
        name: item.name,
        address: item.address,
        lat: item.lat,
        lng: item.lng,
      },
      selectionType: type,
    });
  };

  const renderItem = ({ item }: { item: SearchResult }) => (
    <TouchableOpacity style={styles.resultItem} onPress={() => handleSelect(item)}>
      <Icon name="location-outline" size={20} color={COLORS.subtext} />
      <View style={styles.resultInfo}>
        <Text style={styles.resultName}>{item.name}</Text>
        <Text style={styles.resultAddress}>
          {item.address}
          {item.category ? ` · ${item.category}` : ''}
        </Text>
      </View>
    </TouchableOpacity>
  );

  const renderEmpty = () => {
    if (loading) {
      return (
        <View style={styles.emptyContainer}>
          <ActivityIndicator size="small" color={COLORS.primary} />
        </View>
      );
    }
    return (
      <View style={styles.emptyContainer}>
        <Text style={styles.emptyText}>
          {searched ? '검색 결과가 없습니다' : '장소를 검색해보세요'}
        </Text>
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.safe}>
      {/* Search Bar */}
      <View style={styles.searchBarRow} onLayout={handleLayout}>
        <TouchableOpacity
          onPress={() => navigation.goBack()}
          hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Icon name="arrow-back" size={24} color={COLORS.text} />
        </TouchableOpacity>

        <View style={styles.inputContainer}>
          <TextInput
            ref={inputRef}
            style={styles.input}
            placeholder={type === 'departure' ? '출발지 검색' : '도착지 검색'}
            placeholderTextColor="#AAAAAA"
            value={query}
            onChangeText={setQuery}
            onSubmitEditing={handleSubmit}
            returnKeyType="search"
          />
          {query.length > 0 && (
            <TouchableOpacity
              onPress={() => {
                setQuery('');
                setResults([]);
                setSearched(false);
              }}
              hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
              <Icon name="close-circle" size={18} color="#AAAAAA" />
            </TouchableOpacity>
          )}
        </View>

        <TouchableOpacity onPress={handleSubmit} style={styles.searchIconButton}>
          <Icon name="search" size={22} color={COLORS.primary} />
        </TouchableOpacity>
      </View>

      {/* Results */}
      <FlatList
        data={results}
        keyExtractor={(item, index) => `${item.name}-${item.lat}-${index}`}
        renderItem={renderItem}
        ListEmptyComponent={renderEmpty}
        keyboardShouldPersistTaps="handled"
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  searchBarRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 10,
    gap: 10,
  },
  inputContainer: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F5F5F5',
    borderRadius: 12,
    height: 44,
    paddingHorizontal: 14,
  },
  input: {
    flex: 1,
    fontSize: 15,
    color: COLORS.text,
    padding: 0,
  },
  searchIconButton: {
    padding: 8,
  },
  resultItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderBottomWidth: 0.5,
    borderBottomColor: '#EEEEEE',
    gap: 12,
  },
  resultInfo: {
    flex: 1,
  },
  resultName: {
    fontSize: 15,
    fontWeight: '600',
    color: COLORS.text,
  },
  resultAddress: {
    fontSize: 13,
    color: COLORS.subtext,
    marginTop: 2,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingTop: 80,
  },
  emptyText: {
    fontSize: 14,
    color: '#AAAAAA',
  },
});
