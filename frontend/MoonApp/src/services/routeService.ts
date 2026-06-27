import { toCamelCase } from '../utils/caseConverter';
import { getErrorMessage } from '../utils/errorHandler';
import type { RouteData } from '../types/route';
import type { ApiResponse } from '../types/api';
import type { Place } from '../types/navigation';

export const BASE_URL = 'https://backend-production-1a0a.up.railway.app/api';
const ROUTE_LOAD_ERROR = '경로를 불러오지 못했습니다. 네트워크 연결 또는 서버 상태를 확인한 뒤 다시 시도하세요.';

/** Extract route data from various response shapes (double-wrapped, flat, etc.) */
function extractRouteData(rawJson: any): RouteData {
  const json: ApiResponse<any> = toCamelCase(rawJson);

  if (json.status === 'ERROR') {
    const code = json.error?.code ?? '';
    throw new Error(code ? getErrorMessage(code) : ROUTE_LOAD_ERROR);
  }

  let data = json.data;

  // Double-wrap detection: Spring Boot wraps again if parseJson fails to unwrap.
  if (data && data.status && data.data) {
    data = data.data;
  }

  if (!data || typeof data !== 'object') {
    throw new Error(ROUTE_LOAD_ERROR);
  }

  if (!data.routeId && !data.route_id) {
    throw new Error(ROUTE_LOAD_ERROR);
  }

  return data as RouteData;
}

export async function fetchRoute(
  origin: Place,
  destination: Place,
): Promise<RouteData> {
  const requestBody = {
    originLocation: { latitude: origin.lat, longitude: origin.lng },
    destinationLocation: { latitude: destination.lat, longitude: destination.lng },
    destinationName: destination.name,
  };

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}/route`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody),
    });
  } catch (networkErr) {
    console.error('[RouteService] route request failed:', networkErr);
    throw new Error(ROUTE_LOAD_ERROR);
  }

  if (!res.ok) {
    throw new Error(ROUTE_LOAD_ERROR);
  }

  try {
    return extractRouteData(await res.json());
  } catch (err) {
    console.error('[RouteService] route response failed:', err);
    if (err instanceof Error && err.message !== ROUTE_LOAD_ERROR) {
      throw err;
    }
    throw new Error(ROUTE_LOAD_ERROR);
  }
}

export async function fetchRouteById(routeId: string): Promise<RouteData> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}/route/${routeId}`);
  } catch (networkErr) {
    console.error('[RouteService] route lookup failed:', networkErr);
    throw new Error(ROUTE_LOAD_ERROR);
  }

  if (!res.ok) {
    throw new Error(ROUTE_LOAD_ERROR);
  }

  try {
    return extractRouteData(await res.json());
  } catch (err) {
    console.error('[RouteService] route lookup response failed:', err);
    if (err instanceof Error && err.message !== ROUTE_LOAD_ERROR) {
      throw err;
    }
    throw new Error(ROUTE_LOAD_ERROR);
  }
}
