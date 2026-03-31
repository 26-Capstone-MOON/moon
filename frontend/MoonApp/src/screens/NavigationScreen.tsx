import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  Animated,
  Dimensions,
  PanResponder,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/Ionicons';
import type { StackScreenProps } from '@react-navigation/stack';
import { useIsFocused } from '@react-navigation/native';
import { COLORS } from '../constants/colors';
import { vibrateApproach, vibrateArrival, vibrateTurn } from '../services/hapticService';
import { MOCK_ROUTE_RESPONSE } from '../mocks/mockRoute';
import { useRouteStore } from '../stores/useRouteStore';
import { useNavigationStore } from '../stores/useNavigationStore';
import MapView from '../components/map/MapView';
import RoutePolyline from '../components/map/RoutePolyline';
import DpMarker from '../components/map/DpMarker';
import CurrentLocationMarker from '../components/map/CurrentLocationMarker';
import type { RootStackParamList } from '../types/navigation';
import type { DecisionPoint, Location } from '../types/route';

type Props = StackScreenProps<RootStackParamList, 'Navigation'>;

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const SWIPE_THRESHOLD = SCREEN_WIDTH * 0.25;

function getDpIcon(dpType: string): string {
  switch (dpType) {
    case 'DIRECTION_CHANGE': return 'arrow-forward';
    case 'CROSSWALK': return 'walk-outline';
    case 'VIRTUAL': return 'arrow-up';
    case 'ARRIVAL': return 'flag';
    case 'VERTICAL_MOVE': return 'swap-vertical-outline';
    case 'DEPARTURE': return 'navigate-outline';
    default: return 'navigate-outline';
  }
}

function getDpLabel(dpType: string): string {
  switch (dpType) {
    case 'DIRECTION_CHANGE': return '회전';
    case 'CROSSWALK': return '횡단보도';
    case 'VIRTUAL': return '직진';
    case 'ARRIVAL': return '도착';
    case 'DEPARTURE': return '출발';
    case 'VERTICAL_MOVE': return '계단/엘리베이터';
    default: return '안내';
  }
}

function getRouteCoordinates(lineString: any): Location[] {
  if (!lineString?.coordinates) { return []; }
  return lineString.coordinates.map((c: number[]) => ({
    latitude: c[1],
    longitude: c[0],
  }));
}

export default function NavigationScreen({ navigation, route }: Props) {
  const { departure, destination, dpList: paramDpList } = route.params;
  const dpList = paramDpList.length > 0 ? paramDpList : MOCK_ROUTE_RESPONSE.decisionPoints;

  const routeData = useRouteStore(s => s.routeData);
  const { currentDpIndex, setCurrentDp } = useNavigationStore();
  const isFocused = useIsFocused();

  const [localIndex, setLocalIndex] = useState(currentDpIndex);
  const [isNavigating, setIsNavigating] = useState(true);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const translateX = useRef(new Animated.Value(0)).current;

  // Reset translateX when returning from ProgressScreen
  useEffect(() => {
    if (isFocused) {
      translateX.setValue(0);
    }
  }, [isFocused, translateX]);

  const currentDP: DecisionPoint | undefined = dpList[localIndex];
  const nextDP: DecisionPoint | undefined = dpList[localIndex + 1];
  const isLastDP = localIndex >= dpList.length - 1;
  const progress = dpList.length > 0 ? ((localIndex + 1) / dpList.length) * 100 : 0;

  const lineCoords = getRouteCoordinates(
    routeData?.routeLineString ?? MOCK_ROUTE_RESPONSE.routeLineString,
  );

  // Sync local index to store
  useEffect(() => {
    if (currentDP) {
      setCurrentDp(localIndex, currentDP.dpId);
    }
  }, [localIndex, currentDP, setCurrentDp]);

  // Haptic on DP change
  useEffect(() => {
    if (!currentDP || !isNavigating) { return; }
    if (currentDP.dpType === 'ARRIVAL') {
      vibrateArrival();
    } else if (currentDP.dpType === 'DIRECTION_CHANGE') {
      vibrateTurn();
    } else {
      vibrateApproach();
    }
  }, [localIndex, currentDP, isNavigating]);

  // Auto-progress mock (pause when not focused)
  useEffect(() => {
    if (!isNavigating || isLastDP || !isFocused) { return; }
    timerRef.current = setTimeout(() => {
      setLocalIndex(prev => Math.min(prev + 1, dpList.length - 1));
    }, 5000);
    return () => {
      if (timerRef.current) { clearTimeout(timerRef.current); }
    };
  }, [localIndex, isNavigating, isLastDP, isFocused, dpList.length]);

  const handleStop = useCallback(() => {
    setIsNavigating(false);
    if (timerRef.current) { clearTimeout(timerRef.current); }
    useNavigationStore.getState().reset();
    navigation.popToTop();
  }, [navigation]);

  const handlePrev = () => {
    if (localIndex > 0) { setLocalIndex(prev => prev - 1); }
  };

  const handleNext = () => {
    if (!isLastDP) { setLocalIndex(prev => prev + 1); }
  };

  const navigateToProgressRef = useRef(() => {
    navigation.navigate('Progress', { departure, destination, dpList });
  });
  navigateToProgressRef.current = () => {
    navigation.navigate('Progress', { departure, destination, dpList });
  };

  // Swipe gesture for Progress screen transition (swipe left)
  const panResponder = useRef(
    PanResponder.create({
      onMoveShouldSetPanResponder: (_, gs) =>
        Math.abs(gs.dx) > 20 && Math.abs(gs.dx) > Math.abs(gs.dy),
      onPanResponderMove: (_, gs) => {
        if (gs.dx < 0) { translateX.setValue(gs.dx); }
      },
      onPanResponderRelease: (_, gs) => {
        if (gs.dx < -SWIPE_THRESHOLD) {
          Animated.timing(translateX, {
            toValue: -SCREEN_WIDTH,
            duration: 200,
            useNativeDriver: true,
          }).start(() => {
            translateX.setValue(0);
            navigateToProgressRef.current();
          });
        } else {
          Animated.spring(translateX, {
            toValue: 0,
            useNativeDriver: true,
          }).start();
        }
      },
    }),
  ).current;

  // Clamp localIndex if it goes out of bounds
  useEffect(() => {
    if (dpList.length > 0 && localIndex >= dpList.length) {
      setLocalIndex(dpList.length - 1);
    }
  }, [localIndex, dpList.length]);

  if (!currentDP) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <Text style={{ color: COLORS.subtext }}>경로 정보를 불러오는 중...</Text>
        </View>
      </SafeAreaView>
    );
  }

  // Map camera center on current DP
  const cameraLat = currentDP.location.latitude;
  const cameraLng = currentDP.location.longitude;

  return (
    <Animated.View
      style={[styles.root, { transform: [{ translateX }] }]}
      {...panResponder.panHandlers}>
      <SafeAreaView style={styles.safe}>
        {/* Top Bar */}
        <View style={styles.topBar}>
          <TouchableOpacity onPress={handleStop} style={styles.closeBtn}>
            <Icon name="close" size={24} color={COLORS.text} />
          </TouchableOpacity>
          <View style={styles.topCenter}>
            <View style={styles.dpIconWrap}>
              <Icon name={getDpIcon(currentDP.dpType)} size={20} color="#FFFFFF" />
            </View>
            <Text style={styles.topLabel}>{getDpLabel(currentDP.dpType)}</Text>
          </View>
          <View style={styles.progressBadge}>
            <Text style={styles.progressBadgeText}>{Math.round(progress)}%</Text>
          </View>
        </View>

        {/* Thin progress bar */}
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: `${progress}%` }]} />
        </View>

        {/* Map Area - upper 45% */}
        <View style={styles.mapContainer}>
          <MapView
            camera={{
              latitude: cameraLat,
              longitude: cameraLng,
              zoom: 16,
            }}>
            <RoutePolyline
              coordinates={lineCoords}
              progress={localIndex / Math.max(dpList.length - 1, 1)}
            />
            {dpList.map((dp, i) => (
              <DpMarker key={dp.dpId} dp={dp} index={i} isActive={i === localIndex} />
            ))}
            <CurrentLocationMarker
              latitude={currentDP.location.latitude}
              longitude={currentDP.location.longitude}
            />
          </MapView>

          {/* Mock DP controls overlay */}
          <View style={styles.mockOverlay}>
            <TouchableOpacity
              style={[styles.mockBtn, localIndex === 0 && styles.mockBtnDisabled]}
              onPress={handlePrev}
              disabled={localIndex === 0}>
              <Icon name="chevron-back" size={16} color={localIndex === 0 ? '#CCC' : COLORS.primary} />
            </TouchableOpacity>
            <Text style={styles.dpCounter}>{localIndex + 1}/{dpList.length}</Text>
            <TouchableOpacity
              style={[styles.mockBtn, isLastDP && styles.mockBtnDisabled]}
              onPress={handleNext}
              disabled={isLastDP}>
              <Icon name="chevron-forward" size={16} color={isLastDP ? '#CCC' : COLORS.primary} />
            </TouchableOpacity>
          </View>
        </View>

        {/* Panorama placeholder */}
        <View style={styles.panoramaSection}>
          <View style={styles.panoramaPlaceholder}>
            <Icon name="image-outline" size={20} color="#B0B0B0" />
            <Text style={styles.panoramaText}>Street View</Text>
          </View>
        </View>

        {/* Guide Card */}
        <View style={styles.guideCard}>
          {currentDP.selectedLandmark && (
            <View style={styles.landmarkRow}>
              <Icon name="location" size={14} color={COLORS.primary} />
              <Text style={styles.landmarkName}>{currentDP.selectedLandmark.name}</Text>
              {currentDP.selectedLandmark.position && (
                <View style={styles.positionBadge}>
                  <Text style={styles.positionText}>
                    {currentDP.selectedLandmark.position === 'LEFT' ? '왼쪽' :
                     currentDP.selectedLandmark.position === 'RIGHT' ? '오른쪽' : '전방'}
                  </Text>
                </View>
              )}
            </View>
          )}

          <Text style={styles.guideText}>{currentDP.guidance?.primary}</Text>

          {nextDP && (
            <View style={styles.nextHintRow}>
              <Icon name="arrow-forward-circle-outline" size={14} color={COLORS.subtext} />
              <Text style={styles.nextHintText} numberOfLines={1}>
                다음: {nextDP.guidance?.primary}
              </Text>
            </View>
          )}

          {/* Action buttons */}
          <View style={styles.actionRow}>
            <TouchableOpacity style={styles.btnOutline} activeOpacity={0.7}>
              <Icon name="volume-high-outline" size={18} color={COLORS.primary} />
              <Text style={styles.btnOutlineText}>음성안내</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.btnFilled} activeOpacity={0.7}>
              <Icon name="chatbubble-ellipses-outline" size={18} color="#FFFFFF" />
              <Text style={styles.btnFilledText}>질문하기</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Swipe hint */}
        <View style={styles.swipeHint}>
          <Icon name="chevron-back" size={12} color={COLORS.subtext} />
          <Text style={styles.swipeHintText}>스와이프하여 진행 상황 보기</Text>
        </View>

        {/* Arrived overlay */}
        {isLastDP && currentDP.dpType === 'ARRIVAL' && (
          <View style={styles.arrivedOverlay}>
            <View style={styles.arrivedCard}>
              <View style={styles.arrivedIconWrap}>
                <Icon name="flag" size={32} color={COLORS.primary} />
              </View>
              <Text style={styles.arrivedTitle}>목적지에 도착했습니다</Text>
              <Text style={styles.arrivedSub}>{destination.name}</Text>
              <TouchableOpacity style={styles.arrivedBtn} onPress={handleStop}>
                <Text style={styles.arrivedBtnText}>안내 종료</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}
      </SafeAreaView>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  safe: {
    flex: 1,
    backgroundColor: COLORS.background,
  },

  // Top Bar
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: COLORS.card,
    elevation: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
  },
  closeBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#F5F5F5',
    justifyContent: 'center',
    alignItems: 'center',
  },
  topCenter: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  dpIconWrap: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: COLORS.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  topLabel: {
    fontSize: 17,
    fontWeight: 'bold',
    color: COLORS.text,
  },
  progressBadge: {
    backgroundColor: '#E8ECF8',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  progressBadgeText: {
    fontSize: 13,
    fontWeight: '700',
    color: COLORS.primary,
  },

  // Progress track
  progressTrack: {
    height: 3,
    backgroundColor: '#EEEEEE',
  },
  progressFill: {
    height: 3,
    backgroundColor: COLORS.primary,
    borderRadius: 1.5,
  },

  // Map
  mapContainer: {
    flex: 1,
    minHeight: 200,
  },
  mockOverlay: {
    position: 'absolute',
    bottom: 12,
    alignSelf: 'center',
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.95)',
    borderRadius: 20,
    paddingHorizontal: 6,
    paddingVertical: 4,
    elevation: 3,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.12,
    shadowRadius: 4,
    gap: 6,
  },
  mockBtn: {
    width: 30,
    height: 30,
    borderRadius: 15,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#F5F5F5',
  },
  mockBtnDisabled: {
    backgroundColor: '#FAFAFA',
  },
  dpCounter: {
    fontSize: 13,
    fontWeight: '600',
    color: COLORS.text,
    minWidth: 36,
    textAlign: 'center',
  },

  // Panorama
  panoramaSection: {
    paddingHorizontal: 16,
    paddingTop: 8,
  },
  panoramaPlaceholder: {
    height: 72,
    borderRadius: 14,
    backgroundColor: '#F3F4F6',
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 6,
    borderWidth: 1,
    borderColor: '#E8E8E8',
    borderStyle: 'dashed',
  },
  panoramaText: {
    fontSize: 13,
    color: '#B0B0B0',
    fontWeight: '500',
  },

  // Guide Card
  guideCard: {
    marginHorizontal: 16,
    marginTop: 10,
    padding: 18,
    backgroundColor: COLORS.card,
    borderRadius: 18,
    elevation: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.1,
    shadowRadius: 10,
  },
  landmarkRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    marginBottom: 6,
  },
  landmarkName: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.primary,
  },
  positionBadge: {
    backgroundColor: '#E8ECF8',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
    marginLeft: 4,
  },
  positionText: {
    fontSize: 11,
    fontWeight: '600',
    color: COLORS.primary,
  },
  guideText: {
    fontSize: 18,
    fontWeight: 'bold',
    color: COLORS.text,
    lineHeight: 26,
  },
  nextHintRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 8,
  },
  nextHintText: {
    fontSize: 12,
    color: COLORS.subtext,
    flex: 1,
  },
  actionRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 14,
  },
  btnOutline: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 12,
    borderRadius: 24,
    borderWidth: 1.5,
    borderColor: COLORS.primary,
    backgroundColor: COLORS.card,
  },
  btnOutlineText: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.primary,
  },
  btnFilled: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 12,
    borderRadius: 24,
    backgroundColor: COLORS.primary,
  },
  btnFilledText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFFFFF',
  },

  // Swipe hint
  swipeHint: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    paddingVertical: 8,
    marginBottom: 4,
  },
  swipeHintText: {
    fontSize: 11,
    color: COLORS.subtext,
  },

  // Arrived overlay
  arrivedOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.45)',
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 32,
  },
  arrivedCard: {
    backgroundColor: COLORS.card,
    borderRadius: 24,
    padding: 32,
    alignItems: 'center',
    width: '100%',
  },
  arrivedIconWrap: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#E8ECF8',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  arrivedTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: COLORS.text,
  },
  arrivedSub: {
    fontSize: 14,
    color: COLORS.subtext,
    marginTop: 4,
  },
  arrivedBtn: {
    backgroundColor: COLORS.primary,
    paddingHorizontal: 40,
    paddingVertical: 14,
    borderRadius: 28,
    marginTop: 24,
  },
  arrivedBtnText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
});
