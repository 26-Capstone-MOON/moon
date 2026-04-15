import { create } from 'zustand';

type NavigationState =
  | 'ON_ROUTE'
  | 'DEVIATION_SUSPECTED'
  | 'DEVIATION_WARNING'
  | 'DEVIATION_CONFIRMED'
  | 'RETURNING'
  | 'REROUTING'
  | 'ARRIVED';

type Trigger =
  | 'PRE_ALERT'
  | 'ARRIVAL'
  | 'CONFIRMATION'
  | 'DEVIATION_WARNING'
  | 'REROUTING'
  | 'RETURN_DETECTED'
  | null;

interface Progress {
  completedDps: string[];
  currentDpId: string;
  remainingDps: string[];
  distanceRemaining: number;
  timeRemaining: number;
}

interface NavigationStoreState {
  currentDpIndex: number;
  currentDpId: string | null;
  navigationState: NavigationState;
  trigger: Trigger;
  distanceToDp: number;
  progress: Progress | null;
  guidance: {
    primary: string;
    preAlert: string | null;
    action: string | null;
    primaryAudio: string | null;
    preAlertAudio: string | null;
  } | null;

  setCurrentDp: (index: number, dpId: string) => void;
  setNavigationState: (state: NavigationState) => void;
  setTrigger: (trigger: Trigger) => void;
  setDistanceToDp: (distance: number) => void;
  setProgress: (progress: Progress) => void;
  setGuidance: (guidance: { primary: string; preAlert: string | null; action: string | null; primaryAudio?: string | null; preAlertAudio?: string | null }) => void;
  updateFromTracking: (response: {
    navigationState: NavigationState;
    currentDpId: string;
    distanceToDp: number;
    trigger: Trigger;
    guidance: { primary: string; preAlert: string | null; action: string | null; primaryAudio?: string | null; preAlertAudio?: string | null } | null;
    progress: Progress;
  }) => void;
  reset: () => void;
}

export const useNavigationStore = create<NavigationStoreState>((set) => ({
  currentDpIndex: 0,
  currentDpId: null,
  navigationState: 'ON_ROUTE',
  trigger: null,
  distanceToDp: 0,
  progress: null,
  guidance: null,

  setCurrentDp: (index, dpId) => set({ currentDpIndex: index, currentDpId: dpId }),

  setNavigationState: (navigationState) => set({ navigationState }),

  setTrigger: (trigger) => set({ trigger }),

  setDistanceToDp: (distanceToDp) => set({ distanceToDp }),

  setProgress: (progress) => set({ progress }),

  setGuidance: (guidance) => set({
    guidance: {
      ...guidance,
      primaryAudio: guidance.primaryAudio ?? null,
      preAlertAudio: guidance.preAlertAudio ?? null,
    },
  }),

  updateFromTracking: (response) =>
    set({
      navigationState: response.navigationState,
      currentDpId: response.currentDpId,
      distanceToDp: response.distanceToDp,
      trigger: response.trigger,
      guidance: response.guidance ? {
        ...response.guidance,
        primaryAudio: response.guidance.primaryAudio ?? null,
        preAlertAudio: response.guidance.preAlertAudio ?? null,
      } : null,
      progress: response.progress,
    }),

  reset: () =>
    set({
      currentDpIndex: 0,
      currentDpId: null,
      navigationState: 'ON_ROUTE',
      trigger: null,
      distanceToDp: 0,
      progress: null,
      guidance: null,
    }),
}));
