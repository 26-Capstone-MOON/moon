import { toCamelCase } from '../utils/caseConverter';
import { MOCK_ROUTE_RESPONSE } from '../mocks/mockRoute';
import { getErrorMessage } from '../utils/errorHandler';
import type { RouteData } from '../types/route';
import type { ApiResponse } from '../types/api';
import type { Place } from '../types/navigation';

const BASE_URL = 'http://localhost:8080/api';
const USE_MOCK = false;

/** Extract route data from various response shapes (double-wrapped, flat, etc.) */
function extractRouteData(rawJson: any): RouteData {
  const json: ApiResponse<any> = toCamelCase(rawJson);

  console.log('[DEBUG] 변환 후 status:', json.status, '/ data 존재:', !!json.data);

  if (json.status === 'ERROR') {
    const code = json.error?.code ?? '';
    console.error('[DEBUG] 서버 에러 응답:', json.error);
    throw new Error(code ? getErrorMessage(code) : '경로 요청 실패');
  }

  let data = json.data;

  // Double-wrap detection: Spring Boot wraps again if parseJson fails to unwrap
  if (data && data.status && data.data) {
    console.log('[DEBUG] 이중 래핑 감지 → 내부 data 추출');
    data = data.data;
  }

  if (!data || typeof data !== 'object') {
    console.error('[DEBUG] 응답에 data가 없음. rawJson:', JSON.stringify(rawJson).substring(0, 500));
    throw new Error('서버 응답에 경로 데이터가 없습니다');
  }

  // Validate required fields exist
  if (!data.routeId && !data.route_id) {
    console.error('[DEBUG] routeId 없음. data 키:', Object.keys(data));
    throw new Error('경로 데이터 형식이 올바르지 않습니다');
  }

  console.log('[DEBUG] routeId:', data.routeId,
    '/ decisionPoints:', data.decisionPoints?.length ?? 0,
    '/ totalDistance:', data.totalDistance,
    '/ totalTime:', data.totalTime);

  return data as RouteData;
}

export async function fetchRoute(
  origin: Place,
  destination: Place,
): Promise<RouteData> {
  if (USE_MOCK) {
    return MOCK_ROUTE_RESPONSE;
  }

  const requestBody = {
    originLocation: { latitude: origin.lat, longitude: origin.lng },
    destinationLocation: { latitude: destination.lat, longitude: destination.lng },
    destinationName: destination.name,
  };
  const url = `${BASE_URL}/route`;
  console.log('[DEBUG] fetchRoute URL:', url);
  console.log('[DEBUG] 요청 body:', JSON.stringify(requestBody));

  let res: Response;
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody),
    });
  } catch (networkErr) {
    console.error('[DEBUG] 네트워크 에러:', networkErr);
    throw new Error(`서버 연결 실패 (${BASE_URL}). Spring Boot가 실행 중인지 확인하세요.`);
  }

  console.log('[DEBUG] HTTP status:', res.status);

  if (!res.ok) {
    let errorBody = '';
    try { errorBody = await res.text(); } catch {}
    console.error('[DEBUG] HTTP 에러:', res.status, errorBody.substring(0, 300));
    throw new Error(`서버 에러 (HTTP ${res.status})`);
  }

  let rawJson: any;
  try {
    rawJson = await res.json();
  } catch (parseErr) {
    console.error('[DEBUG] JSON 파싱 실패:', parseErr);
    throw new Error('서버 응답 파싱 실패');
  }

  console.log('[DEBUG] 원본 응답 키:', Object.keys(rawJson));

  return extractRouteData(rawJson);
}

export async function fetchRouteById(routeId: string): Promise<RouteData> {
  if (USE_MOCK) {
    return MOCK_ROUTE_RESPONSE;
  }

  const res = await fetch(`${BASE_URL}/route/${routeId}`);

  if (!res.ok) {
    throw new Error(`경로 조회 실패 (HTTP ${res.status})`);
  }

  const rawJson = await res.json();
  return extractRouteData(rawJson);
}
