import { useCallback } from 'react';
import { fetchRoute, fetchRouteById } from '../services/routeService';
import { useRouteStore } from '../stores/useRouteStore';
import type { Place } from '../types/navigation';

interface UseRouteReturn {
  loadRoute: (origin: Place, destination: Place) => Promise<void>;
  loadRouteById: (routeId: string) => Promise<void>;
}

export function useRoute(): UseRouteReturn {
  const setRouteData = useRouteStore((s) => s.setRouteData);
  const setLoading = useRouteStore((s) => s.setLoading);
  const setError = useRouteStore((s) => s.setError);

  const loadRoute = useCallback(
    async (origin: Place, destination: Place) => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchRoute(origin, destination);
        setRouteData(data);
      } catch (e: unknown) {
        const message = e instanceof Error ? e.message : '경로 요청 실패';
        setError(message);
      } finally {
        setLoading(false);
      }
    },
    [setRouteData, setLoading, setError],
  );

  const loadRouteById = useCallback(
    async (routeId: string) => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchRouteById(routeId);
        setRouteData(data);
      } catch (e: unknown) {
        const message = e instanceof Error ? e.message : '경로 조회 실패';
        setError(message);
      } finally {
        setLoading(false);
      }
    },
    [setRouteData, setLoading, setError],
  );

  return { loadRoute, loadRouteById };
}
