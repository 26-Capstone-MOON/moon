import type { DPItem, Place, RouteInfo } from '../types/navigation';

interface RouteResponse {
  dpList: DPItem[];
  routeInfo: RouteInfo | null;
  polyline: { lat: number; lng: number }[];
}

export async function getRoute(
  _start: Place,
  _end: Place,
): Promise<RouteResponse> {
  // TODO: Spring Boot API 연결 시 실제 호출로 교체
  return {
    dpList: [],
    routeInfo: null,
    polyline: [],
  };
}
