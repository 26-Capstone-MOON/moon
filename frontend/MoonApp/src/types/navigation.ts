export interface Place {
  name: string;
  address: string;
  distance?: string;
  lat: number;
  lng: number;
}

export interface SearchResult {
  name: string;
  address: string;
  category: string;
  lat: number;
  lng: number;
}

import type { DecisionPoint } from './route';

export interface DPItem {
  dp_id: string;
  lat: number;
  lng: number;
  turn_type: number;
  category: string;
  description: string;
  landmark_name?: string;
  distance_to_next: number;
}

export interface RouteInfo {
  totalTime: number;
  totalDistance: number;
  totalSteps: number;
}

export type RootStackParamList = {
  Home: { selectedPlace?: Place; selectionType?: 'departure' | 'destination' } | undefined;
  Search: { type: 'departure' | 'destination' };
  RouteConfirm: { departure: Place; destination: Place };
  Navigation: { departure: Place; destination: Place; dpList: DecisionPoint[] };
  Progress: undefined;
};
