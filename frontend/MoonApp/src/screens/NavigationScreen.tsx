import React, { useEffect, useRef, useState } from 'react';
import {
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/Ionicons';
import type { StackScreenProps } from '@react-navigation/stack';
import { COLORS } from '../constants/colors';
import { vibrateApproach, vibrateArrival, vibrateTurn } from '../services/hapticService';
import { MOCK_ROUTE_RESPONSE } from '../mocks/mockRoute';
import type { RootStackParamList } from '../types/navigation';
import type { DecisionPoint } from '../types/route';

type Props = StackScreenProps<RootStackParamList, 'Navigation'>;

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

export default function NavigationScreen({ navigation, route }: Props) {
  const { departure, destination, dpList: paramDpList } = route.params;
  const dpList = paramDpList.length > 0 ? paramDpList : MOCK_ROUTE_RESPONSE.decisionPoints;
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isNavigating, setIsNavigating] = useState(true);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const currentDP: DecisionPoint | undefined = dpList[currentIndex];
  const nextDP: DecisionPoint | undefined = dpList[currentIndex + 1];
  const isLastDP = currentIndex >= dpList.length - 1;
  const progress = dpList.length > 0 ? ((currentIndex + 1) / dpList.length) * 100 : 0;

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
  }, [currentIndex, currentDP, isNavigating]);

  // Auto-progress mock (simulates walking, every 5s)
  useEffect(() => {
    if (!isNavigating || isLastDP) { return; }
    timerRef.current = setTimeout(() => {
      setCurrentIndex(prev => prev + 1);
    }, 5000);
    return () => {
      if (timerRef.current) { clearTimeout(timerRef.current); }
    };
  }, [currentIndex, isNavigating, isLastDP]);

  const handleNext = () => {
    if (!isLastDP) {
      setCurrentIndex(prev => prev + 1);
    }
  };

  const handlePrev = () => {
    if (currentIndex > 0) {
      setCurrentIndex(prev => prev - 1);
    }
  };

  const handleStop = () => {
    setIsNavigating(false);
    if (timerRef.current) { clearTimeout(timerRef.current); }
    navigation.goBack();
  };

  if (!currentDP) { return null; }

  return (
    <SafeAreaView style={styles.safe}>
      {/* Top Bar: Direction Indicator */}
      <View style={styles.topBar}>
        <TouchableOpacity onPress={handleStop} style={styles.closeButton}>
          <Icon name="close" size={24} color={COLORS.text} />
        </TouchableOpacity>
        <View style={styles.directionInfo}>
          <Icon name={getDpIcon(currentDP.dpType)} size={28} color={COLORS.primary} />
          <Text style={styles.directionLabel}>{getDpLabel(currentDP.dpType)}</Text>
        </View>
        <View style={styles.progressBadge}>
          <Text style={styles.progressText}>{Math.round(progress)}%</Text>
        </View>
      </View>

      {/* Progress Bar */}
      <View style={styles.progressBarBg}>
        <View style={[styles.progressBarFill, { width: `${progress}%` }]} />
      </View>

      {/* Center: Map Placeholder */}
      <View style={styles.mapArea}>
        <Icon name="map-outline" size={48} color="#CCCCCC" />
        <Text style={styles.mapPlaceholderText}>지도 영역</Text>
        <Text style={styles.mapSubText}>Naver Map SDK 연동 예정</Text>

        {/* Manual DP controls (mock) */}
        <View style={styles.mockControls}>
          <TouchableOpacity
            style={[styles.mockButton, currentIndex === 0 && styles.mockButtonDisabled]}
            onPress={handlePrev}
            disabled={currentIndex === 0}>
            <Icon name="chevron-back" size={20} color={currentIndex === 0 ? '#CCCCCC' : COLORS.primary} />
            <Text style={[styles.mockButtonText, currentIndex === 0 && styles.mockButtonTextDisabled]}>이전</Text>
          </TouchableOpacity>
          <Text style={styles.dpCounter}>{currentIndex + 1} / {dpList.length}</Text>
          <TouchableOpacity
            style={[styles.mockButton, isLastDP && styles.mockButtonDisabled]}
            onPress={handleNext}
            disabled={isLastDP}>
            <Text style={[styles.mockButtonText, isLastDP && styles.mockButtonTextDisabled]}>다음</Text>
            <Icon name="chevron-forward" size={20} color={isLastDP ? '#CCCCCC' : COLORS.primary} />
          </TouchableOpacity>
        </View>
      </View>

      {/* Bottom: Panorama Placeholder */}
      <View style={styles.panoramaCard}>
        <View style={styles.panoramaPlaceholder}>
          <Icon name="image-outline" size={24} color="#BBBBBB" />
          <Text style={styles.panoramaText}>거리뷰</Text>
        </View>
      </View>

      {/* Bottom: Guidance Card */}
      <View style={styles.guidanceCard}>
        <View style={styles.guidanceContent}>
          {currentDP.landmarks[0] && (
            <View style={styles.landmarkRow}>
              <Icon name="pin-outline" size={14} color={COLORS.primary} />
              <Text style={styles.landmarkText}>{currentDP.landmarks[0].name}</Text>
            </View>
          )}
          <Text style={styles.guidanceText}>{currentDP.guideText}</Text>
          {nextDP && (
            <Text style={styles.nextHint}>
              다음: {nextDP.guideText}
            </Text>
          )}
        </View>
        <View style={styles.ttsButton}>
          <Icon name="volume-high-outline" size={22} color="#CCCCCC" />
        </View>
      </View>

      {/* Arrived overlay */}
      {isLastDP && currentDP.dpType === 'ARRIVAL' && (
        <View style={styles.arrivedOverlay}>
          <View style={styles.arrivedCard}>
            <Icon name="flag" size={36} color={COLORS.primary} />
            <Text style={styles.arrivedTitle}>목적지에 도착했습니다</Text>
            <Text style={styles.arrivedSub}>{destination.name}</Text>
            <TouchableOpacity style={styles.arrivedButton} onPress={handleStop}>
              <Text style={styles.arrivedButtonText}>안내 종료</Text>
            </TouchableOpacity>
          </View>
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

  // Top Bar
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: COLORS.background,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
  },
  closeButton: {
    padding: 4,
  },
  directionInfo: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    marginLeft: 12,
    gap: 8,
  },
  directionLabel: {
    fontSize: 18,
    fontWeight: 'bold',
    color: COLORS.text,
  },
  progressBadge: {
    backgroundColor: '#F0F4FF',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  progressText: {
    fontSize: 13,
    fontWeight: '600',
    color: COLORS.primary,
  },

  // Progress Bar
  progressBarBg: {
    height: 3,
    backgroundColor: '#EEEEEE',
  },
  progressBarFill: {
    height: 3,
    backgroundColor: COLORS.primary,
  },

  // Map Area
  mapArea: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#F5F5F5',
  },
  mapPlaceholderText: {
    fontSize: 16,
    color: '#BBBBBB',
    marginTop: 8,
  },
  mapSubText: {
    fontSize: 12,
    color: '#CCCCCC',
    marginTop: 4,
  },
  mockControls: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 24,
    gap: 16,
  },
  mockButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.background,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    elevation: 1,
    gap: 4,
  },
  mockButtonDisabled: {
    elevation: 0,
    backgroundColor: '#F0F0F0',
  },
  mockButtonText: {
    fontSize: 14,
    fontWeight: '500',
    color: COLORS.primary,
  },
  mockButtonTextDisabled: {
    color: '#CCCCCC',
  },
  dpCounter: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.text,
  },

  // Panorama
  panoramaCard: {
    paddingHorizontal: 16,
    paddingTop: 8,
  },
  panoramaPlaceholder: {
    height: 80,
    borderRadius: 12,
    backgroundColor: '#F0F0F0',
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 6,
  },
  panoramaText: {
    fontSize: 13,
    color: '#BBBBBB',
  },

  // Guidance Card
  guidanceCard: {
    flexDirection: 'row',
    alignItems: 'center',
    margin: 16,
    marginTop: 8,
    padding: 16,
    backgroundColor: COLORS.background,
    borderRadius: 16,
    elevation: 3,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
  },
  guidanceContent: {
    flex: 1,
  },
  landmarkRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginBottom: 4,
  },
  landmarkText: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.primary,
  },
  guidanceText: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.text,
    lineHeight: 22,
  },
  nextHint: {
    fontSize: 12,
    color: COLORS.subtext,
    marginTop: 6,
  },
  ttsButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#F0F4FF',
    justifyContent: 'center',
    alignItems: 'center',
    marginLeft: 12,
  },

  // Arrived Overlay
  arrivedOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.4)',
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 32,
  },
  arrivedCard: {
    backgroundColor: COLORS.background,
    borderRadius: 20,
    padding: 32,
    alignItems: 'center',
    width: '100%',
  },
  arrivedTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: COLORS.text,
    marginTop: 12,
  },
  arrivedSub: {
    fontSize: 14,
    color: COLORS.subtext,
    marginTop: 4,
  },
  arrivedButton: {
    backgroundColor: COLORS.primary,
    paddingHorizontal: 32,
    paddingVertical: 14,
    borderRadius: 12,
    marginTop: 20,
  },
  arrivedButtonText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: 'bold',
  },
});
