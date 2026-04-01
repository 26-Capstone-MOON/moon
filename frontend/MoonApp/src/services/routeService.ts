import { toCamelCase } from '../utils/caseConverter';
import { MOCK_ROUTE_RESPONSE } from '../mocks/mockRoute';
import { getErrorMessage } from '../utils/errorHandler';
import type { RouteData } from '../types/route';
import type { ApiResponse } from '../types/api';
import type { Place } from '../types/navigation';

const BASE_URL = 'http://10.0.2.2:8080/api';
const USE_MOCK = true;

export async function fetchRoute(
  origin: Place,
  destination: Place,
): Promise<RouteData> {
  if (USE_MOCK) {
    return MOCK_ROUTE_RESPONSE;
  }

  const res = await fetch(`${BASE_URL}/route`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      originLocation: { latitude: origin.lat, longitude: origin.lng },
      destinationLocation: { latitude: destination.lat, longitude: destination.lng },
      destinationName: destination.name,
    }),
  });

  const json: ApiResponse<RouteData> = toCamelCase(await res.json());

  if (json.status === 'ERROR') {
    const code = json.error?.code ?? '';
    throw new Error(code ? getErrorMessage(code) : '경로 요청 실패');
  }

  return json.data!;
}

export async function fetchRouteById(routeId: string): Promise<RouteData> {
  if (USE_MOCK) {
    return MOCK_ROUTE_RESPONSE;
  }

  const res = await fetch(`${BASE_URL}/route/${routeId}`);
  const json: ApiResponse<RouteData> = toCamelCase(await res.json());

  if (json.status === 'ERROR') {
    const code = json.error?.code ?? '';
    throw new Error(code ? getErrorMessage(code) : '경로 조회 실패');
  }

  return json.data!;
}
