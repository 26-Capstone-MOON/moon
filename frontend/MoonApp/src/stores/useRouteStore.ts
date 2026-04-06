import { create } from 'zustand';
import type { RouteData, DecisionPoint } from '../types/route';

interface RouteState {
  routeData: RouteData | null;
  decisionPoints: DecisionPoint[];
  loading: boolean;
  error: string | null;

  setRouteData: (data: RouteData) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useRouteStore = create<RouteState>((set) => ({
  routeData: null,
  decisionPoints: [],
  loading: false,
  error: null,

  setRouteData: (data) => {
    if (!data) {
      console.error('[RouteStore] setRouteData called with null/undefined');
      set({ error: '경로 데이터가 비어있습니다', loading: false });
      return;
    }
    set({
      routeData: data,
      decisionPoints: data.decisionPoints ?? [],
      error: null,
    });
  },

  setLoading: (loading) => set({ loading }),

  setError: (error) => set({ error, loading: false }),

  reset: () =>
    set({
      routeData: null,
      decisionPoints: [],
      loading: false,
      error: null,
    }),
}));
