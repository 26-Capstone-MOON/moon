import React, { useEffect, useMemo, useState } from 'react';
import {
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/Ionicons';
import { NaverMapView, NaverMapMarkerOverlay } from '@mj-studio/react-native-naver-map';
import type { StackScreenProps } from '@react-navigation/stack';
import { COLORS } from '../constants/colors';
import { fetchRoute } from '../services/routeService';
import type { RootStackParamList } from '../types/navigation';
import type { RouteData, DecisionPoint } from '../types/route';
import { formatDistance } from '../utils/formatDistance';
import { formatTime } from '../utils/formatTime';

type Props = StackScreenProps<RootStackParamList, 'RouteConfirm'>;

export default function RouteConfirmScreen({ navigation, route }: Props) {
  const { departure, destination } = route.params;
  const [routeData, setRouteData] = useState<RouteData | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    async function loadRoute() {
      setIsLoading(true);
      try {
        const data = await fetchRoute(departure, destination);
        setRouteData(data);
      } catch {
        // fallback: keep empty
      } finally {
        setIsLoading(false);
      }
    }
    loadRoute();
  }, [departure, destination]);

  const dpList = routeData?.decisionPoints ?? [];

  const handleStart = () => {
    navigation.navigate('Navigation', { departure, destination, dpList });
  };

  const mapCamera = useMemo(() => ({
    latitude: (departure.lat + destination.lat) / 2,
    longitude: (departure.lng + destination.lng) / 2,
    zoom: 14,
  }), [departure, destination]);

  return (
    <SafeAreaView style={styles.safe}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity
          onPress={() => navigation.goBack()}
          hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Icon name="arrow-back" size={24} color={COLORS.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>경로 미리보기</Text>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}>

        {/* Destination Info */}
        <Text style={styles.destName}>{destination.name}</Text>

        <View style={styles.infoTagRow}>
          <Text style={styles.infoTag}>{routeData ? formatTime(routeData.totalTime) : '--분'}</Text>
          <Text style={styles.infoDivider}>|</Text>
          <Text style={styles.infoTag}>{routeData ? formatDistance(routeData.totalDistance) : '--m'}</Text>
        </View>

        {/* Naver Map */}
        <View style={styles.mapContainer}>
          <NaverMapView
            style={styles.map}
            initialCamera={mapCamera}
            isShowCompass
            isShowZoomControls={false}
            isShowLocationButton={false}
          >
            <NaverMapMarkerOverlay
              latitude={departure.lat}
              longitude={departure.lng}
              width={24}
              height={24}
              caption={{ text: '출발', textSize: 12, color: '#34C759' }}
            />
            <NaverMapMarkerOverlay
              latitude={destination.lat}
              longitude={destination.lng}
              width={24}
              height={24}
              caption={{ text: '도착', textSize: 12, color: '#FF3B30' }}
            />
          </NaverMapView>
        </View>

        {/* DP Timeline */}
        <View style={styles.timeline}>
          {/* Start */}
          <TimelineNode
            icon="ellipse"
            iconColor="#34C759"
            label={departure.name}
            sub="출발지에서 출발"
            showLine
          />

          {dpList.length === 0 ? (
            <TimelineNode
              icon="ellipse"
              iconColor={COLORS.primary}
              label={isLoading ? '경로 정보를 불러오는 중...' : '경로 정보 없음'}
              sub=""
              showLine
              faded
            />
          ) : (
            dpList.map((dp, index) => (
              <TimelineNode
                key={dp.dpId}
                number={index + 1}
                label={dp.guideText || '안내 정보 로딩 중...'}
                sub={dp.landmarks[0]?.name || ''}
                showLine={index < dpList.length - 1}
              />
            ))
          )}

          {/* End */}
          <TimelineNode
            icon="ellipse"
            iconColor="#FF3B30"
            label={destination.name}
            sub="도착"
            showLine={false}
          />
        </View>
      </ScrollView>

      {/* Start Button */}
      <View style={styles.bottomContainer}>
        <TouchableOpacity style={styles.startButton} onPress={handleStart}>
          <Text style={styles.startButtonText}>안내 시작하기 →</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

interface TimelineNodeProps {
  number?: number;
  icon?: string;
  iconColor?: string;
  label: string;
  sub: string;
  distance?: string;
  showLine: boolean;
  faded?: boolean;
}

function TimelineNode({ number, icon, iconColor, label, sub, distance, showLine, faded }: TimelineNodeProps) {
  return (
    <View style={styles.nodeContainer}>
      <View style={styles.nodeLeft}>
        {icon ? (
          <View style={[styles.iconCircle, { backgroundColor: iconColor }]}>
            <Icon name={icon} size={12} color="#FFFFFF" />
          </View>
        ) : (
          <View style={styles.numberCircle}>
            <Text style={styles.numberText}>{number}</Text>
          </View>
        )}
        {showLine && <View style={styles.connectorLine} />}
      </View>

      <View style={styles.nodeRight}>
        <Text style={[styles.nodeLabel, faded && styles.fadedText]}>{label}</Text>
        {sub !== '' && <Text style={styles.nodeSub}>{sub}</Text>}
        {distance && <Text style={styles.nodeDistance}>{distance}</Text>}
      </View>
    </View>
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
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: COLORS.text,
  },
  headerSpacer: {
    width: 24,
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingBottom: 100,
  },

  // Destination Info
  destName: {
    fontSize: 20,
    fontWeight: 'bold',
    color: COLORS.text,
    marginTop: 8,
  },
  infoTagRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 10,
    gap: 8,
  },
  infoTag: {
    fontSize: 14,
    color: COLORS.primary,
    fontWeight: '500',
  },
  infoDivider: {
    fontSize: 14,
    color: '#DDDDDD',
  },

  // Map
  mapContainer: {
    height: 220,
    borderRadius: 12,
    overflow: 'hidden',
    marginTop: 20,
  },
  map: {
    flex: 1,
  },

  // Timeline
  timeline: {
    marginTop: 24,
  },
  nodeContainer: {
    flexDirection: 'row',
  },
  nodeLeft: {
    width: 28,
    alignItems: 'center',
  },
  iconCircle: {
    width: 28,
    height: 28,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
  },
  numberCircle: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: COLORS.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  numberText: {
    fontSize: 13,
    fontWeight: 'bold',
    color: '#FFFFFF',
  },
  connectorLine: {
    width: 2,
    flex: 1,
    backgroundColor: COLORS.primary,
    minHeight: 32,
  },
  nodeRight: {
    flex: 1,
    paddingLeft: 14,
    paddingBottom: 20,
  },
  nodeLabel: {
    fontSize: 15,
    fontWeight: '600',
    color: COLORS.text,
  },
  nodeSub: {
    fontSize: 13,
    color: COLORS.subtext,
    marginTop: 2,
  },
  nodeDistance: {
    fontSize: 12,
    color: COLORS.primary,
    marginTop: 4,
  },
  fadedText: {
    color: '#AAAAAA',
  },

  // Bottom Button
  bottomContainer: {
    paddingHorizontal: 20,
    paddingBottom: 24,
    paddingTop: 12,
    backgroundColor: COLORS.background,
  },
  startButton: {
    backgroundColor: COLORS.primary,
    height: 52,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  startButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
});
