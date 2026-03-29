import { toCamelCase } from '../utils/caseConverter';
import type { ApiResponse } from '../types/api';
import type { Location } from '../types/route';

const BASE_URL = 'http://10.0.2.2:8080/api';
const USE_MOCK = true;

// --- Mock Responses ---

const MOCK_PANORAMA_RESPONSE = {
  status: 'SUCCESS' as const,
  data: { updated: true, matchedCount: 3 },
};

const MOCK_REROUTE_RESPONSE = {
  routeId: 'mock-reroute-001',
  isRerouted: true,
  previousRouteId: 'mock-route-001',
  totalDistance: 800,
  totalTime: 600,
  routeLineString: {
    type: 'LineString',
    coordinates: [
      [126.9802, 37.569],
      [126.981, 37.5701],
      [126.9815, 37.5708],
    ],
  },
  decisionPoints: [
    {
      dpId: 'reroute-dp-1',
      dpType: 'DIRECTION_CHANGE',
      location: { latitude: 37.569, longitude: 126.9802 },
      guideText: '국민은행 앞에서 우회전하세요',
      landmarks: [{ name: '국민은행', position: 'RIGHT' as const, category: 'BK9' }],
    },
    {
      dpId: 'reroute-dp-2',
      dpType: 'CROSSWALK',
      location: { latitude: 37.5701, longitude: 126.981 },
      guideText: '횡단보도를 건너세요',
      landmarks: [],
    },
    {
      dpId: 'reroute-dp-3',
      dpType: 'ARRIVAL',
      location: { latitude: 37.5708, longitude: 126.9815 },
      guideText: '목적지에 도착했습니다',
      landmarks: [],
    },
  ],
};

const MOCK_CONVERSATION_RESPONSE = {
  message: '현재 GS25 편의점을 지나 직진 중이에요. 약 200m 앞에서 우회전하시면 됩니다. 주변에 스타벅스가 보이면 올바른 길이에요.',
  guidanceUpdated: false,
};

// --- API Functions ---

export async function uploadPanoramaResults(
  routeId: string,
  results: { dpId: string; visionResults: { label: string; confidence: number }[] }[],
): Promise<{ updated: boolean; matchedCount: number }> {
  if (USE_MOCK) {
    return MOCK_PANORAMA_RESPONSE.data;
  }

  const res = await fetch(`${BASE_URL}/route/${routeId}/panorama-results`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ results }),
  });

  const json: ApiResponse<{ updated: boolean; matchedCount: number }> = toCamelCase(await res.json());

  if (json.status === 'ERROR') {
    throw new Error(json.error?.message ?? '파노라마 결과 업로드 실패');
  }

  return json.data!;
}

export async function requestReroute(
  routeId: string,
  currentLocation: Location,
): Promise<typeof MOCK_REROUTE_RESPONSE> {
  if (USE_MOCK) {
    return MOCK_REROUTE_RESPONSE;
  }

  const res = await fetch(`${BASE_URL}/route/${routeId}/reroute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ currentLocation }),
  });

  const json: ApiResponse<typeof MOCK_REROUTE_RESPONSE> = toCamelCase(await res.json());

  if (json.status === 'ERROR') {
    throw new Error(json.error?.message ?? '재경로 탐색 실패');
  }

  return json.data!;
}

export async function sendConversation(
  routeId: string,
  message: string,
  context?: { currentDpId: string; navigationState: string },
): Promise<{ message: string; guidanceUpdated: boolean }> {
  if (USE_MOCK) {
    return MOCK_CONVERSATION_RESPONSE;
  }

  const res = await fetch(`${BASE_URL}/route/${routeId}/conversation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, context }),
  });

  const json: ApiResponse<{ message: string; guidanceUpdated: boolean }> = toCamelCase(await res.json());

  if (json.status === 'ERROR') {
    throw new Error(json.error?.message ?? '대화 요청 실패');
  }

  return json.data!;
}
