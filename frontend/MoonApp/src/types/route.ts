export interface Location {
  latitude: number;
  longitude: number;
}

export interface Landmark {
  name: string;
  position: 'LEFT' | 'RIGHT' | 'FRONT';
  category?: string;
}

export interface DecisionPoint {
  dpId: string;
  dpType: string;
  location: Location;
  guideText: string;
  landmarks: Landmark[];
  panoramaUrl?: string;
}

export interface RouteData {
  routeId: string;
  totalDistance: number;
  totalTime: number;
  weather?: any;
  routeLineString: any;
  decisionPoints: DecisionPoint[];
}
