import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import {
  Animated,
  DeviceEventEmitter,
  Dimensions,
  PanResponder,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import WebView from 'react-native-webview';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/Ionicons';
import type { StackScreenProps } from '@react-navigation/stack';
import { useIsFocused } from '@react-navigation/native';
import BottomSheet, { BottomSheetScrollView } from '@gorhom/bottom-sheet';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import Reanimated, { useAnimatedStyle, useSharedValue, withTiming, interpolate, Extrapolation } from 'react-native-reanimated';
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
import AssistantBottomSheet from '../components/chat/AssistantBottomSheet';
// requestReroute import removed — reroute handled by WebSocket server
import { toCamelCase } from '../utils/caseConverter';
// extractErrorMessage import removed — no longer used after reroute cleanup
import type { RootStackParamList } from '../types/navigation';
import { formatTime } from '../utils/formatTime';
import { formatDistance } from '../utils/formatDistance';
import { buildPanoramaHtml, getPrimaryPan } from '../utils/panoramaUtils';
import {
  startWidget,
  updateWidget,
  stopWidget,
  dpTypeToArrowType,
  type WidgetState,
} from '../services/widgetService';
import type { DecisionPoint, Location } from '../types/route';

type Props = StackScreenProps<RootStackParamList, 'Navigation'>;

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');
const SWIPE_THRESHOLD = SCREEN_WIDTH * 0.25;

// Bottom sheet snap points
const SNAP_MIN = 0.55;  // 55% - default (panorama fully visible)
const SNAP_MID = 0.75;  // 75%
const SNAP_MAX = 0.90;  // 90%

// Panorama height range (driven by bottom sheet position)
const PANO_HEIGHT_MIN = 200;
const PANO_HEIGHT_MAX = 260;

// Header icon: routed through the same arrow-type classifier as the lock-screen
// widget (see widgetService.dpTypeToArrowType) so that LEFT/RIGHT/U turns,
// crosswalks, vertical moves, and straight segments stay visually consistent
// between the in-app header and the background widget.
function getDpIcon(dp: DecisionPoint): string {
  switch (dpTypeToArrowType(dp)) {
    case 'left': return 'arrow-back';
    case 'right': return 'arrow-forward';
    case 'crosswalk': return 'walk-outline';
    case 'vertical_move': return 'swap-vertical-outline';
    case 'arrived': return 'flag';
    case 'warning': return 'warning';
    case 'straight':
    default: return 'arrow-up';
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
  if (Array.isArray(lineString)) {
    return lineString.map((pt: any) => ({
      latitude: pt.latitude,
      longitude: pt.longitude,
    }));
  }
  if (lineString?.coordinates) {
    return lineString.coordinates.map((c: number[]) => ({
      latitude: c[1],
      longitude: c[0],
    }));
  }
  return [];
}

export default function NavigationScreen({ navigation, route }: Props) {
  const { departure, destination, dpList: paramDpList } = route.params;
  const storeDpList = useRouteStore(s => s.decisionPoints) ?? [];
  const dpList = useMemo(() => {
    if (storeDpList.length > 0) { return storeDpList; }
    if (paramDpList?.length > 0) { return paramDpList; }
    return MOCK_ROUTE_RESPONSE.decisionPoints;
  }, [storeDpList, paramDpList]);

  const routeData = useRouteStore(s => s.routeData);
  const setRouteData = useRouteStore(s => s.setRouteData);
  const { currentDpIndex, setCurrentDp, navigationState, trigger } = useNavigationStore();
  const updateFromTracking = useNavigationStore(s => s.updateFromTracking);
  const guidance = useNavigationStore(s => s.guidance);
  const currentDpId = useNavigationStore(s => s.currentDpId);
  const isFocused = useIsFocused();

  // GPS tracking
  const { position, startTracking, stopTracking } = useLocation();

  const [localIndex, setLocalIndex] = useState(currentDpIndex);
  const [isNavigating, setIsNavigating] = useState(true);
  const [toastVisible, setToastVisible] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [isRerouting, setIsRerouting] = useState(false);
  const [panoReady, setPanoReady] = useState(false);
  const [panoEnabled, _setPanoEnabled] = useState(true);
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [isAssistantOpen, setIsAssistantOpen] = useState(false);
  const isAssistantOpenRef = useRef(false);
  useEffect(() => {
    isAssistantOpenRef.current = isAssistantOpen;
  }, [isAssistantOpen]);
  // 잠금화면 위젯 "질문하기" 트리거 카운터. 증가할 때마다 AssistantBottomSheet의
  // STT가 자동 시작된다. 첫 트리거 = 1, 두 번째 = 2 ...
  const [micRequestCounter, setMicRequestCounter] = useState(0);
  // AssistantBottomSheet 내부 STT가 켜진 상태인지. 위젯 title/body/액션 라벨을
  // "듣고 있어요" 상태로 갈아끼울 때 사용.
  const [isAssistantListening, setIsAssistantListening] = useState(false);
  const [isFollowing, setIsFollowing] = useState(true);
  const followTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showError = useCallback((msg: string) => {
    setToastMessage(msg);
    setToastVisible(true);
  }, []);

  // When user touches/zooms the map, pause camera following for 5 seconds
  const handleCameraChanged = useCallback((params: { reason: string }) => {
    if (params.reason === 'Gesture' || params.reason === 'Control') {
      setIsFollowing(false);
      if (followTimerRef.current) { clearTimeout(followTimerRef.current); }
      followTimerRef.current = setTimeout(() => setIsFollowing(true), 5000);
    }
  }, []);

  const handleRecenter = useCallback(() => {
    if (followTimerRef.current) { clearTimeout(followTimerRef.current); }
    setIsFollowing(true);
  }, []);

  // WebSocket connection
  const handleWsMessage = useCallback((data: unknown) => {
    // Unwrap {status, data} wrapper if present (Python ApiResponse envelope)
    let payload: any = data;
    if (payload && typeof payload === 'object' && 'status' in payload && 'data' in payload) {
      console.log('[WS] ApiResponse 래퍼 감지 → data 필드 추출');
      payload = (payload as any).data;
    }
    const camelData = toCamelCase(payload) as any;

    // Reroute response from WebSocket (has routeId + decisionPoints = new route data)
    if (camelData.routeId && camelData.decisionPoints) {
      console.log('[WS] 재경로 응답 수신 → routeStore 업데이트, routeId:', camelData.routeId);
      setRouteData(camelData);
      setLocalIndex(0);
      setIsRerouting(false);
      return;
    }

    console.log('[WS] trigger:', camelData.trigger, '/ state:', camelData.navigationState,
      '/ dpDist:', camelData.distanceToDp?.toFixed?.(1),
      '/ guidance:', camelData.guidance?.primary?.substring(0, 30));

    // DEVIATION_CONFIRMED → show rerouting UI (actual reroute handled by WebSocket server)
    if (camelData.navigationState === 'DEVIATION_CONFIRMED') {
      setIsRerouting(true);
    }

    updateFromTracking(camelData);
  }, [updateFromTracking, setRouteData]);

  const { connectionState, send, connect, disconnect } = useWebSocket({
    url: 'wss://backend-production-1a0a.up.railway.app/api/tracking',
    onMessage: handleWsMessage,
    onError: (msg) => showError(msg),
  });
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // rerouteCalledRef removed — reroute handled by WebSocket server
  const translateX = useRef(new Animated.Value(0)).current;
  const bottomSheetRef = useRef<BottomSheet>(null);

  const snapPoints = useMemo(() => [
    Math.round(SCREEN_HEIGHT * SNAP_MIN),
    Math.round(SCREEN_HEIGHT * SNAP_MID),
    Math.round(SCREEN_HEIGHT * SNAP_MAX),
  ], []);

  const sheetIndex = useSharedValue(0);

  const handleSheetChange = useCallback((index: number) => {
    sheetIndex.value = withTiming(index, { duration: 200 });
  }, [sheetIndex]);

  const panoramaAnimStyle = useAnimatedStyle(() => {
    const height = interpolate(
      sheetIndex.value,
      [0, 1, 2],
      [PANO_HEIGHT_MIN, 160, PANO_HEIGHT_MAX],
      Extrapolation.CLAMP,
    );
    return { height };
  });

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

  // Widget lifecycle: start on first DP, update on DP change
  const widgetStartedRef = useRef(false);
  useEffect(() => {
    if (!currentDP) { return; }
    const totalDPs = dpList.length;
    const progressPct = totalDPs > 1
      ? Math.round((localIndex / (totalDPs - 1)) * 100)
      : 0;

    const dpTypes = dpList.map(dp => dpTypeToArrowType(dp));

    // 잠금화면에서 어시스턴트 STT가 켜진 상태 → 위젯을 "듣고 있어요" 상태로 갈아끼움.
    // 이건 deviation/rerouting/returning 보다도 우선순위가 높다 (사용자가 능동적으로 트리거).
    if (isAssistantListening) {
      updateWidget({
        label: '듣고 있어요',
        primary: '질문을 말씀해주세요...',
        next: undefined,
        arrowType: dpTypeToArrowType(currentDP),
        progress: progressPct,
        currentIndex: localIndex,
        totalCount: totalDPs,
        dpTypes,
        isListening: true,
      }).catch(() => {});
      return;
    }

    // Deviation / rerouting / returning — override DP-based widget state
    if (navigationState === 'DEVIATION_WARNING' || navigationState === 'DEVIATION_CONFIRMED') {
      updateWidget({
        label: '경로 확인',
        primary: '경로를 벗어난 것 같아요',
        next: undefined,
        arrowType: 'warning',
        progress: progressPct,
        currentIndex: localIndex,
        totalCount: totalDPs,
        dpTypes,
      }).catch(() => {});
      return;
    }

    if (navigationState === 'REROUTING') {
      updateWidget({
        label: '경로 재탐색',
        primary: '경로를 다시 찾고 있어요',
        next: undefined,
        arrowType: 'warning',
        progress: progressPct,
        currentIndex: localIndex,
        totalCount: totalDPs,
        dpTypes,
      }).catch(() => {});
      return;
    }

    if (trigger === 'RETURN_DETECTED') {
      updateWidget({
        label: '복귀 중',
        primary: '다시 돌아오고 있어요',
        next: undefined,
        arrowType: 'straight',
        progress: progressPct,
        currentIndex: localIndex,
        totalCount: totalDPs,
        dpTypes,
      }).catch(() => {});
      return;
    }

    const nextLandmarkName = nextDP?.selectedLandmark?.name;
    const fallbackLabel = getDpLabel(currentDP.dpType);
    const arrowType = dpTypeToArrowType(currentDP);
    console.log('[Widget] dpTypes:', dpTypes.slice(0, 5), '...total', dpTypes.length);
    console.log('[Widget]', {
      currentIndex: localIndex,
      totalCount: totalDPs,
      arrowType,
      progress: progressPct,
    });
    const state: WidgetState = {
      label: (currentDP.guidance as any)?.alertLabel ?? fallbackLabel,
      primary: currentDP.guidance?.primary ?? '',
      next: nextLandmarkName,
      arrowType,
      progress: progressPct,
      currentIndex: localIndex,
      totalCount: totalDPs,
      dpTypes,
    };

    if (!widgetStartedRef.current) {
      widgetStartedRef.current = true;
      startWidget(state).catch(err => console.warn('startWidget failed', err));
    } else {
      updateWidget(state).catch(err => console.warn('updateWidget failed', err));
    }
  }, [currentDP, nextDP, localIndex, dpList.length, navigationState, trigger, isAssistantListening]);

  // Stop widget on unmount
  useEffect(() => {
    return () => {
      stopWidget().catch(err => console.warn('stopWidget failed', err));
    };
  }, []);

  // Mock 모드: 출발지 DP일 때 store에 ARRIVAL trigger 주입 → trigger-based TTS가 처리
  const hasFiredDeparture = useRef(false);
  useEffect(() => {
    if (hasFiredDeparture.current) { return; }
    if (connectionState === 'CONNECTED') { return; }
    if (!currentDP || currentDP.dpType !== 'DEPARTURE' || localIndex !== 0) { return; }
    hasFiredDeparture.current = true;
    useNavigationStore.getState().setTrigger('ARRIVAL');
    useNavigationStore.getState().setGuidance({
      primary: currentDP.guidance?.primary ?? '',
      preAlert: currentDP.guidance?.preAlert ?? null,
      action: currentDP.guidance?.action ?? null,
      primaryAudio: currentDP.guidance?.primaryAudio ?? null,
    });
  }, [currentDP, connectionState, localIndex]);

  // TTS on trigger change (deduplicated by trigger + dpId)
  const lastSpokenKey = useRef<string | null>(null);
  useEffect(() => {
    if (!trigger) {
      lastSpokenKey.current = null;
      return;
    }
    const spokenKey = `${trigger}_${currentDpId ?? ''}`;
    if (lastSpokenKey.current === spokenKey) { return; }

    // 재라우팅 중에는 DP 안내 트리거 무시 (이탈/재라우팅 안내만 허용)
    if (isRerouting && (trigger === 'PRE_ALERT' || trigger === 'ARRIVAL' || trigger === 'CONFIRMATION')) {
      console.log('[TTS] 재라우팅 중 DP 안내 무시:', trigger);
      return;
    }

    console.log('[TTS] trigger 감지:', trigger, '/ dpId:', currentDpId);
    let text: string | null = null;
    let audio: string | null = null;
    switch (trigger) {
      case 'PRE_ALERT':
        text = guidance?.preAlert ?? guidance?.primary ?? null;
        audio = guidance?.preAlertAudio ?? guidance?.primaryAudio ?? null;
        break;
      case 'ARRIVAL':
        text = guidance?.primary ?? null;
        audio = guidance?.primaryAudio ?? null;
        break;
      case 'CONFIRMATION':
        text = guidance?.primary ?? '잘 가고 있어요';
        audio = guidance?.primaryAudio ?? null;
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
      lastSpokenKey.current = spokenKey;
      console.log('[TTS] 재생:', text, audio ? '(Google TTS)' : '(device TTS)');
      if (ttsEnabled && !isAssistantOpenRef.current) {
        ttsStop();
        ttsSpeak(text, audio);
      } else if (isAssistantOpenRef.current) {
        console.log('[TTS] 어시스턴트 열림 → 자동 안내 TTS 스킵');
      }
    }
  }, [trigger, guidance, currentDpId, ttsEnabled, isRerouting]);

  // Sync localIndex from server's currentDpId.
  // Card advance (idx > localIndex) only fires on ARRIVAL/CONFIRMATION trigger.
  // PRE_ALERT plays TTS only — does NOT switch the card.
  // Backward sync (idx < localIndex) always allowed for reroute / rewind cases.
  useEffect(() => {
    if (!currentDpId || connectionState !== 'CONNECTED') { return; }
    const idx = dpList.findIndex(dp => dp.dpId === currentDpId);
    if (idx < 0) { return; }
    if (idx > localIndex && trigger !== 'ARRIVAL' && trigger !== 'CONFIRMATION') {
      return;
    }
    if (idx !== localIndex) {
      console.log('[NAV] 서버 DP 동기화:', currentDpId, '/ index:', idx, '/ trigger:', trigger);
      setLocalIndex(idx);
    }
  }, [currentDpId, trigger, dpList, connectionState, localIndex]);

  // Auto-progress mock — only when WebSocket is NOT connected
  useEffect(() => {
    if (!isNavigating || isLastDP || !isFocused) { return; }
    if (connectionState === 'CONNECTED') { return; }
    timerRef.current = setTimeout(() => {
      setLocalIndex(prev => Math.min(prev + 1, dpList.length - 1));
    }, 15000);
    return () => {
      if (timerRef.current) { clearTimeout(timerRef.current); }
    };
  }, [localIndex, isNavigating, isLastDP, isFocused, dpList.length, connectionState]);

  // handleReroute removed — reroute is handled by WebSocket server automatically

  // Send GPS to server via WebSocket when position updates
  useEffect(() => {
    if (!position || connectionState !== 'CONNECTED' || !routeData?.routeId) {
      console.log('[WS] GPS 미전송 - position:', !!position, '/ ws:', connectionState, '/ routeId:', routeData?.routeId);
      return;
    }
    console.log('[WS] GPS 전송:', position.latitude.toFixed(6), position.longitude.toFixed(6));
    send({
      route_id: routeData.routeId,
      latitude: position.latitude,
      longitude: position.longitude,
      timestamp: new Date().toISOString(),
      speed: position.speed ?? 0,
    });
  }, [position, connectionState, routeData?.routeId, send]);

  // Delay panorama WebView load to reduce memory pressure on mount
  // Software GPU emulator needs more time for map to stabilize
  useEffect(() => {
    const t = setTimeout(() => setPanoReady(true), 1500);
    return () => clearTimeout(t);
  }, []);

  // Start WebSocket + GPS tracking on mount
  useEffect(() => {
    connect();
    startTracking();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 잠금화면 위젯 "질문하기" 탭 → BroadcastReceiver → DeviceEventEmitter.
  // 시트 자동 오픈 + 카운터 증가로 STT 자동 시작 트리거.
  useEffect(() => {
    const sub = DeviceEventEmitter.addListener('WidgetMicTriggered', () => {
      console.log('[Widget] WidgetMicTriggered received');
      ttsStop();
      setIsAssistantOpen(true);
      setMicRequestCounter(prev => prev + 1);
    });
    return () => sub.remove();
  }, []);

  // Stop auto-progress and tracking when arrived via server state
  useEffect(() => {
    if (navigationState === 'ARRIVED') {
      setIsNavigating(false);
      if (timerRef.current) { clearTimeout(timerRef.current); }
      stopTracking();
      disconnect();
      stopWidget().catch(err => console.warn('stopWidget failed', err));
    }
  }, [navigationState, stopTracking, disconnect]);

  // Delay arrived overlay so user can read the final DP card (~5s).
  // The card stays visible during the delay; cleanup above runs immediately.
  const [showArrivedOverlay, setShowArrivedOverlay] = useState(false);
  useEffect(() => {
    const arrived = (isLastDP && currentDP?.dpType === 'ARRIVAL') || navigationState === 'ARRIVED';
    if (!arrived) {
      setShowArrivedOverlay(false);
      return;
    }
    const t = setTimeout(() => setShowArrivedOverlay(true), 5000);
    return () => clearTimeout(t);
  }, [isLastDP, currentDP, navigationState]);

  // Reroute is handled by WebSocket server (TrackingWebSocketHandler)
  // — no REST call needed from frontend. The reroute response arrives
  // via WebSocket and is detected in handleWsMessage above.

  const handleDismissToast = useCallback(() => setToastVisible(false), []);

  const handleStop = useCallback(() => {
    setIsNavigating(false);
    if (timerRef.current) { clearTimeout(timerRef.current); }
    ttsStop();
    stopTracking();
    disconnect();
    stopWidget().catch(err => console.warn('stopWidget failed', err));
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

  const handleGoProgress = useCallback(() => {
    navigation.navigate('Progress', { departure, destination, dpList });
  }, [navigation, departure, destination, dpList]);

  if (!currentDP) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.loadingContainer}>
          <Text style={{ color: COLORS.subtext }}>경로 정보를 불러오는 중...</Text>
        </View>
      </SafeAreaView>
    );
  }

  // Initial camera: lock to actual route origin (the user's real starting GPS),
  // not dpList[0].location which is the DP marker (~10m offset from origin).
  // Priority: routeData.origin (server-provided) → dpList[0].location → demo fallback.
  // Use wider zoom (15) at first paint — zoom 17 felt cramped on entry.
  // Once GPS arrives AND is within range, the live `camera` prop zooms in to 17.
  const cameraOrigin = useMemo(() => {
    // Demo route origin (matches DEMO_ROUTE_ORIGIN in mock_guidance_final.py).
    // Used only when neither server origin nor dpList[0] is available.
    const DEMO_ORIGIN = { latitude: 37.504879, longitude: 127.025111 };
    const o = routeData?.origin ?? dpList[0]?.location ?? DEMO_ORIGIN;
    return { latitude: o.latitude, longitude: o.longitude };
  }, [routeData, dpList]);
  const initialCamera = useMemo(
    () => ({ latitude: cameraOrigin.latitude, longitude: cameraOrigin.longitude, zoom: 15 }),
    [cameraOrigin],
  );

  // Distance-based GPS filter: the emulator's default GPS often emits a stale
  // value (e.g., Nonhyeon station ~1km away from BurgerKing) for ~2s after
  // mount, which would jerk the camera. Only follow `position` once it is
  // within 500m of the route origin — i.e., a plausible reading near the
  // start. Until then, stick with initialCamera at the origin.
  const positionNearOrigin = useMemo(() => {
    if (!position) { return false; }
    // Haversine in meters (inline to avoid extra import)
    const toRad = (d: number) => (d * Math.PI) / 180;
    const R = 6371000;
    const dLat = toRad(position.latitude - cameraOrigin.latitude);
    const dLng = toRad(position.longitude - cameraOrigin.longitude);
    const a =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(toRad(cameraOrigin.latitude)) *
        Math.cos(toRad(position.latitude)) *
        Math.sin(dLng / 2) ** 2;
    const d = 2 * R * Math.asin(Math.sqrt(a));
    return d <= 500;
  }, [position, cameraOrigin]);

  // Live camera follows GPS once available AND near the route origin. While
  // position is null or far away (emulator default), leave `camera` undefined
  // so the native side keeps initialCamera intact. Skipped if the user has
  // panned/zoomed (isFollowing=false).
  const cameraProps = isFollowing && position && positionNearOrigin ? {
    camera: { latitude: position.latitude, longitude: position.longitude, zoom: 17 },
  } : {};

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
                <Icon name={getDpIcon(currentDP)} size={20} color="#FFFFFF" />
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
              initialCamera={initialCamera}
              {...cameraProps}
              animationDuration={500}
              onCameraChanged={handleCameraChanged}
              mapPadding={{ bottom: Math.round(SCREEN_HEIGHT * SNAP_MIN) + 16, top: 0, left: 0, right: 0 }}>
              <RoutePolyline
                coordinates={lineCoords}
                progress={localIndex / Math.max(dpList.length - 1, 1)}
              />
              {dpList.map((dp, i) => (
                <DpMarker key={dp.dpId} dp={dp} index={i} isActive={i === localIndex} />
              ))}
              <CurrentLocationMarker
                latitude={position?.latitude ?? currentDP.location.latitude}
                longitude={position?.longitude ?? currentDP.location.longitude}
              />
            </MapView>

            {/* Re-center button — shown when user pans/zooms away */}
            {!isFollowing && (
              <TouchableOpacity style={styles.recenterBtn} onPress={handleRecenter}>
                <Icon name="locate" size={22} color={COLORS.primary} />
              </TouchableOpacity>
            )}

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
            onChange={handleSheetChange}
            enablePanDownToClose={false}
            enableOverDrag={false}
            backgroundStyle={styles.sheetBackground}
            handleIndicatorStyle={styles.sheetHandle}
          >
            <BottomSheetScrollView style={styles.sheetContent} showsVerticalScrollIndicator={false}>
              {/* Panorama */}
              <View style={styles.panoramaSection}>
                {(() => { if (currentDP) { console.log('[NAV] pan:', currentDP.dpId, getPrimaryPan(currentDP)); } return null; })()}
                {panoEnabled && panoReady && currentDP && getPrimaryPan(currentDP) !== null ? (
                  <Reanimated.View style={[styles.panoramaPlaceholder, panoramaAnimStyle]}>
                    <WebView
                      key={`pano-${currentDP.dpId}`}
                      source={{
                        html: buildPanoramaHtml(
                          currentDP.panoramaRequest!.location.latitude,
                          currentDP.panoramaRequest!.location.longitude,
                          getPrimaryPan(currentDP)!,
                          currentDP.selectedLandmark?.name ?? null,
                          currentDP.selectedLandmark?.location?.latitude ?? null,
                          currentDP.selectedLandmark?.location?.longitude ?? null,
                        ),
                      }}
                      style={styles.panoramaImage}
                      scrollEnabled={false}
                      nestedScrollEnabled={true}
                      javaScriptEnabled={true}
                      domStorageEnabled={true}
                      originWhitelist={['*']}
                      cacheEnabled={false}
                      incognito={true}
                      androidLayerType="software"
                      onMessage={(e) => {
                        try {
                          const msg = JSON.parse(e.nativeEvent.data);
                          if (msg.type === 'pov_init') {
                            console.log(`[PANO] init: setPov pan=${msg.pan}`);
                          } else if (msg.type === 'pov_reset') {
                            console.log(`[PANO] pano_changed: re-setPov pan=${msg.pan}`);
                          } else if (msg.type === 'pov') {
                            console.log(`[PANO] moved: pan=${Number(msg.pan).toFixed(1)}`);
                          }
                        } catch {}
                      }}
                    />
                  </Reanimated.View>
                ) : (
                  <View style={styles.panoramaLoading}>
                    <Icon name="image-outline" size={18} color="#B0B0B0" />
                    <Text style={styles.panoramaLoadingText}>Street View 로딩 중...</Text>
                  </View>
                )}
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
                  <TouchableOpacity
                    style={[styles.btnOutline, !ttsEnabled && styles.btnOutlineDisabled]}
                    activeOpacity={0.7}
                    onPress={() => {
                      setTtsEnabled(prev => {
                        if (prev) { ttsStop(); }
                        return !prev;
                      });
                    }}>
                    <Icon
                      name={ttsEnabled ? 'volume-high-outline' : 'volume-mute-outline'}
                      size={18}
                      color={ttsEnabled ? COLORS.primary : COLORS.subtext}
                    />
                    <Text style={[styles.btnOutlineText, !ttsEnabled && { color: COLORS.subtext }]}>
                      {ttsEnabled ? '음성안내' : '음성끔'}
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.btnFilled}
                    activeOpacity={0.7}
                    onPress={() => {
                      ttsStop();
                      setIsAssistantOpen(true);
                    }}>
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

          {/* Arrived overlay (delayed 5s so user can see the final DP card first) */}
          {showArrivedOverlay && (
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

          <AssistantBottomSheet
            visible={isAssistantOpen}
            onClose={() => setIsAssistantOpen(false)}
            routeId={routeData?.routeId ?? null}
            currentDpId={currentDpId ?? currentDP?.dpId ?? null}
            autoStartCounter={micRequestCounter}
            onListeningChange={setIsAssistantListening}
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
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
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
  recenterBtn: {
    position: 'absolute',
    bottom: 60,
    right: 12,
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 3,
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
    overflow: 'hidden',
  },
  panoramaImage: {
    flex: 1,
    borderRadius: 14,
    overflow: 'hidden',
  },
  panoramaLoading: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    height: 200,
    borderRadius: 14,
    backgroundColor: '#F3F4F6',
    borderWidth: 1,
    borderColor: '#E8E8E8',
    borderStyle: 'dashed',
  },
  panoramaLoadingText: {
    fontSize: 13,
    fontWeight: '500',
    color: '#B0B0B0',
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
  btnOutlineDisabled: {
    borderColor: COLORS.subtext,
    backgroundColor: COLORS.background,
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
