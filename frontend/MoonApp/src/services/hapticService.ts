import { Vibration } from 'react-native';

// DP 접근 시 짧은 진동
export function vibrateApproach() {
  Vibration.vibrate(200);
}

// 방향 전환 시 패턴 진동 (짧-쉼-짧-쉼-긴)
export function vibrateTurn() {
  Vibration.vibrate([0, 150, 100, 150, 100, 400]);
}

// 도착 시 긴 진동
export function vibrateArrival() {
  Vibration.vibrate(500);
}
