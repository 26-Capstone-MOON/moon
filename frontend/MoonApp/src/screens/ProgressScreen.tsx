import React, { useRef } from 'react';
import {
  Animated,
  Dimensions,
  PanResponder,
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
import { useNavigationStore } from '../stores/useNavigationStore';
import { useRouteStore } from '../stores/useRouteStore';
import { MOCK_ROUTE_RESPONSE } from '../mocks/mockRoute';
import { formatDistance } from '../utils/formatDistance';
import { formatTime } from '../utils/formatTime';
import type { RootStackParamList } from '../types/navigation';
import type { DecisionPoint } from '../types/route';

type Props = StackScreenProps<RootStackParamList, 'Progress'>;

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
    case 'VIRTUAL': return '직진 확인';
    case 'ARRIVAL': return '도착';
    case 'DEPARTURE': return '출발';
    case 'VERTICAL_MOVE': return '계단/엘리베이터';
    default: return '안내';
  }
}

export default function ProgressScreen({ navigation, route }: Props) {
  const { dpList: paramDpList } = route.params;
  const dpList = paramDpList.length > 0 ? paramDpList : MOCK_ROUTE_RESPONSE.decisionPoints;

  const currentDpIndex = useNavigationStore(s => s.currentDpIndex);
  const routeData = useRouteStore(s => s.routeData);

  const totalDistance = routeData?.totalDistance ?? MOCK_ROUTE_RESPONSE.totalDistance;
  const totalTime = routeData?.totalTime ?? MOCK_ROUTE_RESPONSE.totalTime;

  const progress = dpList.length > 0 ? ((currentDpIndex + 1) / dpList.length) * 100 : 0;
  const passedCount = currentDpIndex;
  const remainingCount = dpList.length - currentDpIndex - 1;

  // Estimate remaining distance/time proportionally
  const remainingRatio = dpList.length > 1 ? remainingCount / (dpList.length - 1) : 0;
  const distanceRemaining = Math.round(totalDistance * remainingRatio);
  const timeRemaining = Math.round(totalTime * remainingRatio);

  const translateX = useRef(new Animated.Value(0)).current;

  // Swipe right to go back to Navigation
  const panResponder = useRef(
    PanResponder.create({
      onMoveShouldSetPanResponder: (_, gs) =>
        Math.abs(gs.dx) > 20 && Math.abs(gs.dx) > Math.abs(gs.dy),
      onPanResponderMove: (_, gs) => {
        if (gs.dx > 0) { translateX.setValue(gs.dx); }
      },
      onPanResponderRelease: (_, gs) => {
        if (gs.dx > SWIPE_THRESHOLD) {
          Animated.timing(translateX, {
            toValue: SCREEN_WIDTH,
            duration: 200,
            useNativeDriver: true,
          }).start(() => {
            navigation.goBack();
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

  return (
    <Animated.View
      style={[styles.root, { transform: [{ translateX }] }]}
      {...panResponder.panHandlers}>
      <SafeAreaView style={styles.safe}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
            <Icon name="chevron-back" size={22} color={COLORS.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>경로 진행 상황</Text>
          <View style={styles.headerRight} />
        </View>

        {/* Progress summary card */}
        <View style={styles.summaryCard}>
          <View style={styles.progressCircleWrap}>
            <View style={styles.progressCircle}>
              <Text style={styles.progressPercent}>{Math.round(progress)}%</Text>
            </View>
          </View>
          <View style={styles.summaryStats}>
            <View style={styles.statItem}>
              <Icon name="checkmark-circle" size={16} color="#34C759" />
              <Text style={styles.statValue}>{passedCount}</Text>
              <Text style={styles.statLabel}>완료</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statItem}>
              <Icon name="navigate-circle" size={16} color={COLORS.primary} />
              <Text style={styles.statValue}>1</Text>
              <Text style={styles.statLabel}>현재</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statItem}>
              <Icon name="ellipsis-horizontal-circle" size={16} color={COLORS.subtext} />
              <Text style={styles.statValue}>{remainingCount}</Text>
              <Text style={styles.statLabel}>남음</Text>
            </View>
          </View>

          {/* Full-width progress bar */}
          <View style={styles.fullBarTrack}>
            <View style={[styles.fullBarFill, { width: `${progress}%` }]} />
          </View>
        </View>

        {/* Checkpoint list */}
        <ScrollView style={styles.listScroll} contentContainerStyle={styles.listContent}>
          {dpList.map((dp: DecisionPoint, index: number) => {
            const isPassed = index < currentDpIndex;
            const isCurrent = index === currentDpIndex;

            return (
              <View key={dp.dpId} style={styles.checkpointRow}>
                {/* Timeline */}
                <View style={styles.timeline}>
                  <View style={[
                    styles.dot,
                    isPassed && styles.dotPassed,
                    isCurrent && styles.dotCurrent,
                  ]}>
                    {isPassed ? (
                      <Icon name="checkmark" size={12} color="#FFFFFF" />
                    ) : (
                      <Icon
                        name={getDpIcon(dp.dpType)}
                        size={12}
                        color={isCurrent ? '#FFFFFF' : COLORS.subtext}
                      />
                    )}
                  </View>
                  {index < dpList.length - 1 && (
                    <View style={[styles.line, isPassed && styles.linePassed]} />
                  )}
                </View>

                {/* Content */}
                <View style={[
                  styles.checkpointCard,
                  isCurrent && styles.checkpointCardCurrent,
                ]}>
                  <View style={styles.checkpointHeader}>
                    <Text style={[
                      styles.checkpointType,
                      isPassed && styles.textPassed,
                      isCurrent && styles.textCurrent,
                    ]}>
                      {getDpLabel(dp.dpType)}
                    </Text>
                    {isCurrent && (
                      <View style={styles.currentBadge}>
                        <Text style={styles.currentBadgeText}>현재</Text>
                      </View>
                    )}
                  </View>
                  <Text
                    style={[
                      styles.checkpointGuide,
                      isPassed && styles.textPassedGuide,
                    ]}
                    numberOfLines={2}>
                    {dp.guidance?.primary}
                  </Text>
                  {dp.selectedLandmark && (
                    <View style={styles.checkpointLandmark}>
                      <Icon name="location-outline" size={11} color={COLORS.subtext} />
                      <Text style={styles.checkpointLandmarkText}>
                        {dp.selectedLandmark.name}
                      </Text>
                    </View>
                  )}
                </View>
              </View>
            );
          })}
        </ScrollView>

        {/* Bottom summary */}
        <View style={styles.bottomBar}>
          <View style={styles.bottomItem}>
            <Icon name="walk-outline" size={20} color={COLORS.primary} />
            <View>
              <Text style={styles.bottomValue}>{formatDistance(distanceRemaining)}</Text>
              <Text style={styles.bottomLabel}>남은 거리</Text>
            </View>
          </View>
          <View style={styles.bottomDivider} />
          <View style={styles.bottomItem}>
            <Icon name="time-outline" size={20} color={COLORS.primary} />
            <View>
              <Text style={styles.bottomValue}>{formatTime(timeRemaining)}</Text>
              <Text style={styles.bottomLabel}>예상 시간</Text>
            </View>
          </View>
        </View>

        {/* Swipe hint */}
        <View style={styles.swipeHint}>
          <Text style={styles.swipeHintText}>스와이프하여 내비게이션으로 돌아가기</Text>
          <Icon name="chevron-forward" size={12} color={COLORS.subtext} />
        </View>
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
  },

  // Header
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: COLORS.card,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
  },
  backBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#F5F5F5',
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    flex: 1,
    textAlign: 'center',
    fontSize: 17,
    fontWeight: 'bold',
    color: COLORS.text,
  },
  headerRight: {
    width: 36,
  },

  // Summary card
  summaryCard: {
    margin: 16,
    padding: 20,
    backgroundColor: COLORS.card,
    borderRadius: 18,
    elevation: 3,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
  },
  progressCircleWrap: {
    alignItems: 'center',
    marginBottom: 16,
  },
  progressCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    borderWidth: 4,
    borderColor: COLORS.primary,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#E8ECF8',
  },
  progressPercent: {
    fontSize: 22,
    fontWeight: 'bold',
    color: COLORS.primary,
  },
  summaryStats: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 16,
    marginBottom: 16,
  },
  statItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  statValue: {
    fontSize: 15,
    fontWeight: '700',
    color: COLORS.text,
  },
  statLabel: {
    fontSize: 12,
    color: COLORS.subtext,
  },
  statDivider: {
    width: 1,
    height: 16,
    backgroundColor: '#E0E0E0',
  },
  fullBarTrack: {
    height: 6,
    backgroundColor: '#EEEEEE',
    borderRadius: 3,
  },
  fullBarFill: {
    height: 6,
    backgroundColor: COLORS.primary,
    borderRadius: 3,
  },

  // Checkpoint list
  listScroll: {
    flex: 1,
  },
  listContent: {
    paddingHorizontal: 16,
    paddingBottom: 8,
  },
  checkpointRow: {
    flexDirection: 'row',
  },
  timeline: {
    width: 32,
    alignItems: 'center',
  },
  dot: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#E8E8E8',
    justifyContent: 'center',
    alignItems: 'center',
  },
  dotPassed: {
    backgroundColor: '#34C759',
  },
  dotCurrent: {
    backgroundColor: COLORS.primary,
  },
  line: {
    width: 2,
    flex: 1,
    backgroundColor: '#E0E0E0',
    minHeight: 20,
  },
  linePassed: {
    backgroundColor: '#34C759',
  },

  // Checkpoint card
  checkpointCard: {
    flex: 1,
    marginLeft: 10,
    marginBottom: 12,
    padding: 14,
    backgroundColor: COLORS.card,
    borderRadius: 14,
    elevation: 1,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 3,
  },
  checkpointCardCurrent: {
    borderWidth: 1.5,
    borderColor: COLORS.primary,
    elevation: 3,
    shadowOpacity: 0.1,
  },
  checkpointHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  checkpointType: {
    fontSize: 13,
    fontWeight: '600',
    color: COLORS.subtext,
  },
  textPassed: {
    color: '#34C759',
  },
  textCurrent: {
    color: COLORS.primary,
  },
  currentBadge: {
    backgroundColor: COLORS.primary,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 8,
  },
  currentBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  checkpointGuide: {
    fontSize: 14,
    fontWeight: '500',
    color: COLORS.text,
    lineHeight: 20,
  },
  textPassedGuide: {
    color: COLORS.subtext,
  },
  checkpointLandmark: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    marginTop: 4,
  },
  checkpointLandmarkText: {
    fontSize: 12,
    color: COLORS.subtext,
  },

  // Bottom bar
  bottomBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginHorizontal: 16,
    marginBottom: 4,
    padding: 16,
    backgroundColor: COLORS.card,
    borderRadius: 16,
    elevation: 3,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 6,
  },
  bottomItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flex: 1,
    justifyContent: 'center',
  },
  bottomValue: {
    fontSize: 16,
    fontWeight: 'bold',
    color: COLORS.text,
  },
  bottomLabel: {
    fontSize: 11,
    color: COLORS.subtext,
  },
  bottomDivider: {
    width: 1,
    height: 32,
    backgroundColor: '#E0E0E0',
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
});
