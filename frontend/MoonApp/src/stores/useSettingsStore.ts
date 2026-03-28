import { create } from 'zustand';

interface SettingsState {
  ttsEnabled: boolean;
  hapticEnabled: boolean;
  volume: number;

  setTtsEnabled: (enabled: boolean) => void;
  setHapticEnabled: (enabled: boolean) => void;
  setVolume: (volume: number) => void;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  ttsEnabled: true,
  hapticEnabled: true,
  volume: 1.0,

  setTtsEnabled: (ttsEnabled) => set({ ttsEnabled }),
  setHapticEnabled: (hapticEnabled) => set({ hapticEnabled }),
  setVolume: (volume) => set({ volume: Math.max(0, Math.min(1, volume)) }),
}));
