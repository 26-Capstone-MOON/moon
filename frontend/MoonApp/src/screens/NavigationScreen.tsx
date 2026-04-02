import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
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
import BottomSheet, { BottomSheetScrollView } from '@gorhom/bottom-sheet';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import Reanimated, { useAnimatedStyle, interpolate, useSharedValue } from 'react-native-reanimated';
import { COLORS } from '../constants/colors';
import { speak as ttsSpeak, stop as ttsStop } from '../services/ttsService';
import { vibrateApproach, vibrateArrival, vibrateTurn } from '../services/hapticService';
import { MOCK_ROUTE_RESPONSE } from '../mocks/mockRoute';
import { useRouteStore } from '../stores/useRouteStore';
import { useNavigationStore } from '../stores/useNavigationStore';
import { useWebSocket } from '../hooks/useWebSocket';
import { useLocation } from '../hooks/useLocation';
import MapView from '../components/map/MapView';
import RoutePolyline from '../components/map/RoutePolyline';
import DpMarker from '../components/map/DpMarker';
import CurrentLocationMarker from '../components/map/CurrentLocationMarker';
import DeviationBanner from '../components/guide/DeviationBanner';
import ErrorToast from '../components/common/ErrorToast';
import LoadingOverlay from '../components/common/LoadingOverlay';
import { requestReroute } from '../services/navigationApi';
import { toCamelCase } from '../utils/caseConverter';
import { extractErrorMessage } from '../utils/errorHandler';
import type { RootStackParamList } from '../types/navigation';
import { formatTime } from '../utils/formatTime';
import { formatDistance } from '../utils/formatDistance';
import type { DecisionPoint, Location } from '../types/route';

type Props = StackScreenProps<RootStackParamList, 'Navigation'>;

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');
const SWIPE_THRESHOLD = SCREEN_WIDTH * 0.25;

// Bottom sheet snap points
const SNAP_MIN = 0.55;  // 55% - default (card + progress btn visible)
const SNAP_MID = 0.70;  // 70%
const SNAP_MAX = 0.85;  // 85%

// Panorama height range (interpolated by animatedIndex)
const PANO_HEIGHT_MIN = 72;
const PANO_HEIGHT_MID = 140;
const PANO_HEIGHT_MAX = 260;

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
  const storeDpList = useRouteStore(s => s.decisionPoints);
  const dpList = storeDpList.length > 0 ? storeDpList : (paramDpList.length > 0 ? paramDpList : MOCK_ROUTE_RESPONSE.decisionPoints);

  const routeData = useRouteStore(s => s.routeData);
  const setRouteData = useRouteStore(s => s.setRouteData);
  const { currentDpIndex, setCurrentDp, navigationState, trigger } = useNavigationStore();
  const updateFromTracking = useNavigationStore(s => s.updateFromTracking);
  const isFocused = useIsFocused();

  // GPS tracking
  const { position, startTracking, stopTracking } = useLocation();

  const [localIndex, setLocalIndex] = useState(currentDpIndex);
  const [isNavigating, setIsNavigating] = useState(true);
  const [toastVisible, setToastVisible] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [isRerouting, setIsRerouting] = useState(false);

  const showError = useCallback((msg: string) => {
    setToastMessage(msg);
    setToastVisible(true);
  }, []);

  // WebSocket connection
  const handleWsMessage = useCallback((data: unknown) => {
    const camelData = toCamelCase(data) as Parameters<typeof updateFromTracking>[0];
    updateFromTracking(camelData);
  }, [updateFromTracking]);

  const { connectionState, send, connect, disconnect } = useWebSocket({
    url: 'ws://10.0.2.2:8080/api/tracking',
    onMessage: handleWsMessage,
    onError: (msg) => showError(msg),
  });
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const rerouteCalledRef = useRef(false);
  const translateX = useRef(new Animated.Value(0)).current;
  const bottomSheetRef = useRef<BottomSheet>(null);

  const snapPoints = useMemo(() => [
    Math.round(SCREEN_HEIGHT * SNAP_MIN),
    Math.round(SCREEN_HEIGHT * SNAP_MID),
    Math.round(SCREEN_HEIGHT * SNAP_MAX),
  ], []);

  const animatedIndex = useSharedValue(0);

  const panoramaAnimStyle = useAnimatedStyle(() => ({
    height: interpolate(
      animatedIndex.value,
      [0, 1, 2],
      [PANO_HEIGHT_MIN, PANO_HEIGHT_MID, PANO_HEIGHT_MAX],
    ),
  }));

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

  // TTS on trigger change
  const guidance = useNavigationStore(s => s.guidance);
  useEffect(() => {
    if (!trigger) { return; }
    let text: string | null = null;
    switch (trigger) {
      case 'PRE_ALERT':
        text = guidance?.preAlert ?? guidance?.primary ?? null;
        break;
      case 'ARRIVAL':
        text = guidance?.primary ?? null;
        break;
      case 'CONFIRMATION':
        text = '잘 가고 있어요';
        break;
      case 'DEVIATION_WARNING':
        text = '경로를 벗어난 것 같아요';
        break;
      case 'REROUTING':
        text = '경로를 다시 찾고 있어요';
        break;
      case 'RETURN_DETECTED':
        text = '다시 돌아오고 있어요';
        break;
    }
    if (text) {
      ttsStop();
      ttsSpeak(text);
    }
  }, [trigger, guidance]);

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

  const handleReroute = useCallback(async () => {
    const routeId = routeData?.routeId;
    if (!routeId || isRerouting) { return; }

    const currentLocation = currentDP?.location;
    if (!currentLocation) {
      showError('현재 위치를 가져올 수 없어요');
      return;
    }

    setIsRerouting(true);
    try {
      const result = await requestReroute(routeId, currentLocation);
      const camelResult = toCamelCase(result);
      setRouteData(camelResult);
      setLocalIndex(0);
    } catch (e) {
      showError(extractErrorMessage(e));
    } finally {
      setIsRerouting(false);
      rerouteCalledRef.current = false;
    }
  }, [routeData?.routeId, isRerouting, currentDP?.location, showError, setRouteData]);

  // Send GPS to server via WebSocket when position updates
  useEffect(() => {
    if (!position || connectionState !== 'CONNECTED' || !routeData?.routeId) { return; }
    send({
      route_id: routeData.routeId,
      latitude: position.latitude,
      longitude: position.longitude,
      timestamp: new Date().toISOString(),
      speed: position.speed ?? 0,
    });
  }, [position, connectionState, routeData?.routeId, send]);

  // Start WebSocket + GPS tracking on mount
  useEffect(() => {
    connect();
    startTracking();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Stop auto-progress and tracking when arrived via server state
  useEffect(() => {
    if (navigationState === 'ARRIVED') {
      setIsNavigating(false);
      if (timerRef.current) { clearTimeout(timerRef.current); }
      stopTracking();
      disconnect();
    }
  }, [navigationState, stopTracking, disconnect]);

  // Auto-trigger reroute on DEVIATION_CONFIRMED or REROUTING trigger
  useEffect(() => {
    if (
      (navigationState === 'DEVIATION_CONFIRMED' || trigger === 'REROUTING') &&
      !rerouteCalledRef.current &&
      !isRerouting
    ) {
      rerouteCalledRef.current = true;
      handleReroute();
    }
  }, [navigationState, trigger, isRerouting, handleReroute]);

  const handleDismissToast = useCallback(() => setToastVisible(false), []);

  const handleStop = useCallback(() => {
    setIsNavigating(false);
    if (timerRef.current) { clearTimeout(timerRef.current); }
    ttsStop();
    stopTracking();
    disconnect();
    useNavigationStore.getState().reset();
    useRouteStore.getState().reset();
    navigation.popToTop();
  }, [navigation, stopTracking, disconnect]);

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

  const handleGoProgress = useCallback(() => {
    navigation.navigate('Progress', { departure, destination, dpList });
  }, [navigation, departure, destination, dpList]);

  return (
    <GestureHandlerRootView style={styles.root}>
      <Animated.View
        style={[styles.root, { transform: [{ translateX }] }]}>
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

          {/* Map Area - fills remaining space above bottom sheet */}
          <View style={styles.mapContainer} {...panResponder.panHandlers}>
            <DeviationBanner
              visible={navigationState === 'DEVIATION_WARNING'}
            />
            <MapView
              camera={{
                latitude: cameraLat,
                longitude: cameraLng,
                zoom: 16,
              }}
              mapPadding={{ bottom: 60, top: 0, left: 0, right: 0 }}>
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

          {/* Bottom Sheet */}
          <BottomSheet
            ref={bottomSheetRef}
            index={0}
            snapPoints={snapPoints}
            animatedIndex={animatedIndex}
            enablePanDownToClose={false}
            enableOverDrag={false}
            backgroundStyle={styles.sheetBackground}
            handleIndicatorStyle={styles.sheetHandle}
          >
            <BottomSheetScrollView style={styles.sheetContent} showsVerticalScrollIndicator={false}>
              {/* Panorama placeholder */}
              <View style={styles.panoramaSection}>
                <Reanimated.View style={[styles.panoramaPlaceholder, panoramaAnimStyle]}>
                  <Icon name="image-outline" size={20} color="#B0B0B0" />
                  <Text style={styles.panoramaText}>Street View</Text>
                </Reanimated.View>
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
                    <Icon name="mic-outline" size={18} color="#FFFFFF" />
                    <Text style={styles.btnFilledText}>질문하기</Text>
                  </TouchableOpacity>
                </View>
              </View>

              {/* Progress button */}
              <TouchableOpacity style={styles.progressBtn} onPress={handleGoProgress} activeOpacity={0.7}>
                <Icon name="list-outline" size={14} color={COLORS.primary} />
                <Text style={styles.progressBtnText}>진행 상황 보기</Text>
                <Icon name="chevron-forward" size={14} color={COLORS.primary} />
              </TouchableOpacity>

              {/* Bottom safe area spacing for Android gesture bar */}
              <View style={styles.bottomSafeSpace} />
            </BottomSheetScrollView>
          </BottomSheet>

          {/* Arrived overlay */}
          {((isLastDP && currentDP.dpType === 'ARRIVAL') || navigationState === 'ARRIVED') && (
            <View style={styles.arrivedOverlay}>
              <View style={styles.arrivedCard}>
                <View style={styles.arrivedIconWrap}>
                  <Icon name="flag" size={32} color={COLORS.primary} />
                </View>
                <Text style={styles.arrivedTitle}>목적지에 도착했습니다</Text>
                <Text style={styles.arrivedSub}>{destination.name}</Text>

                {/* Route summary */}
                <View style={styles.summaryRow}>
                  <View style={styles.summaryCard}>
                    <Text style={styles.summaryLabel}>소요 시간</Text>
                    <Text style={styles.summaryValue}>
                      {formatTime(routeData?.totalTime ?? 0)}
                    </Text>
                  </View>
                  <View style={styles.summaryCard}>
                    <Text style={styles.summaryLabel}>이동 거리</Text>
                    <Text style={styles.summaryValue}>
                      {formatDistance(routeData?.totalDistance ?? 0)}
                    </Text>
                  </View>
                </View>

                <TouchableOpacity style={styles.arrivedBtn} onPress={handleStop}>
                  <Text style={styles.arrivedBtnText}>안내 종료</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}

          {isRerouting && <LoadingOverlay message="경로를 다시 찾고 있어요..." />}

          <ErrorToast
            message={toastMessage}
            visible={toastVisible}
            onDismiss={handleDismissToast}
          />
        </SafeAreaView>
      </Animated.View>
    </GestureHandlerRootView>
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

  // Bottom Sheet
  sheetBackground: {
    backgroundColor: COLORS.background,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    elevation: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -3 },
    shadowOpacity: 0.12,
    shadowRadius: 8,
  },
  sheetHandle: {
    backgroundColor: '#D0D0D0',
    width: 40,
    height: 4,
    borderRadius: 2,
  },
  sheetContent: {
    flex: 1,
  },

  // Panorama
  panoramaSection: {
    paddingHorizontal: 16,
    paddingTop: 4,
  },
  panoramaPlaceholder: {
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

  // Progress button
  progressBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginHorizontal: 16,
    marginTop: 10,
    paddingVertical: 10,
    borderRadius: 12,
    backgroundColor: '#E8ECF8',
  },
  progressBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: COLORS.primary,
  },
  bottomSafeSpace: {
    height: 32,
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
  summaryRow: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 20,
    width: '100%',
  },
  summaryCard: {
    flex: 1,
    backgroundColor: '#F5F5F7',
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: 'center',
  },
  summaryLabel: {
    fontSize: 12,
    color: COLORS.subtext,
    marginBottom: 4,
  },
  summaryValue: {
    fontSize: 20,
    fontWeight: 'bold',
    color: COLORS.text,
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
