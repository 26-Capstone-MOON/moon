import { NativeModules } from 'react-native';

const { NavigationNotification } = NativeModules;

export type ArrowType =
  | 'left'
  | 'right'
  | 'straight'
  | 'arrived'
  | 'warning'
  | 'crosswalk'
  | 'vertical_move';

export interface WidgetState {
  label: string;
  primary: string;
  next?: string;
  arrowType: ArrowType;
  progress: number; // 0-100
  currentIndex?: number;
  totalCount?: number;
  dpTypes?: ArrowType[];
  // 잠금화면 위젯에서 STT가 켜진 상태이면 마이크 액션 라벨을
  // "듣는 중"으로 토글하고 title/body를 "듣고 있어요" 안내로 갈아끼우기 위한 플래그.
  isListening?: boolean;
}

export const startWidget = (state: WidgetState): Promise<void> =>
  NavigationNotification.start(state);

export const updateWidget = (state: WidgetState): Promise<void> =>
  NavigationNotification.update(state);

export const stopWidget = (): Promise<void> => NavigationNotification.stop();

// Map a DecisionPoint to a widget arrow icon. Accepts both camelCase
// frontend store and snake_case raw server payload shapes.
export const dpTypeToArrowType = (dp: any): ArrowType => {
  if (!dp) { return 'straight'; }
  const dpType = dp.dpType ?? dp.dp_type;
  const turnType = dp.turnType ?? dp.turn_type;
  const action = dp.guidance?.action;

  if (dpType === 'ARRIVAL') { return 'arrived'; }

  // guidance.action is the most reliable signal
  if (action === 'LEFT_TURN' || action === 'U_TURN') { return 'left'; }
  if (action === 'RIGHT_TURN') { return 'right'; }
  if (action === 'CROSSWALK') { return 'crosswalk'; }
  if (
    action === 'STAIRS_UP' ||
    action === 'STAIRS_DOWN' ||
    action === 'OVERPASS' ||
    action === 'UNDERPASS' ||
    action === 'ELEVATOR'
  ) {
    return 'vertical_move';
  }

  // String turn_type fallback (some servers send labels)
  if (turnType === 'LEFT' || turnType === 'TURN_LEFT') { return 'left'; }
  if (turnType === 'RIGHT' || turnType === 'TURN_RIGHT') { return 'right'; }

  // dpType-based fallback when action is null
  if (dpType === 'CROSSWALK') { return 'crosswalk'; }
  if (dpType === 'VERTICAL_MOVE') { return 'vertical_move'; }

  // VIRTUAL DP and DEPARTURE → straight (consistent with header's arrow-up/navigate-outline)
  return 'straight';
};
