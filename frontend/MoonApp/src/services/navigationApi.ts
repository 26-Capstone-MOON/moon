import { toCamelCase } from '../utils/caseConverter';
import type { ApiResponse } from '../types/api';
import type { Location, RouteData } from '../types/route';

const BASE_URL = 'https://backend-production-1a0a.up.railway.app/api';

async function parseApiResponse<T>(res: Response, fallbackMessage: string): Promise<T> {
  if (!res.ok) {
    throw new Error(fallbackMessage);
  }

  const json: ApiResponse<T> = toCamelCase(await res.json());
  if (json.status === 'ERROR') {
    throw new Error(json.error?.message ?? fallbackMessage);
  }
  if (json.data == null) {
    throw new Error(fallbackMessage);
  }
  return json.data;
}

export async function requestReroute(
  routeId: string,
  currentLocation: Location,
): Promise<RouteData> {
  const res = await fetch(`${BASE_URL}/route/${routeId}/reroute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ currentLocation }),
  });

  return parseApiResponse(res, '경로를 불러오지 못했습니다. 네트워크 연결 또는 서버 상태를 확인한 뒤 다시 시도하세요.');
}

export interface ConversationResult {
  answer: string;
  showPanorama?: boolean;
  targetDpId?: string | null;
}

export async function sendConversation(
  routeId: string,
  question: string,
  options?: { currentDpId?: string; completedDpIds?: string[] },
): Promise<ConversationResult> {
  const res = await fetch(`${BASE_URL}/route/${routeId}/conversation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      currentDpId: options?.currentDpId,
      completedDpIds: options?.completedDpIds,
    }),
  });

  return parseApiResponse(res, '질문 요청에 실패했습니다. 잠시 후 다시 시도하세요.');
}
