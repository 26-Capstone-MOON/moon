export interface Location {
  latitude: number;
  longitude: number;
}

export interface Guidance {
  primary: string;
  preAlert: string | null;
  action:
    | 'RIGHT_TURN'
    | 'LEFT_TURN'
    | 'U_TURN'
    | 'CROSSWALK'
    | 'STAIRS_UP'
    | 'STAIRS_DOWN'
    | 'OVERPASS'
    | 'UNDERPASS'
    | 'ELEVATOR'
    | null;
}

export interface SelectedLandmark {
  name: string;
  categoryCode: string;
  position: 'LEFT' | 'RIGHT' | 'FRONT';
  distance: number;
  score: number;
  matchStatus: 'MATCHED' | 'POI_ONLY' | 'VISION_ONLY';
  isOpen: boolean;
}

export interface PanoramaDirection {
  pan: number;
  label: 'FRONT' | 'LEFT' | 'RIGHT';
  isPrimary: boolean;
}

export interface PanoramaRequest {
  location: Location;
  directions: PanoramaDirection[];
}

export interface DecisionPoint {
  dpId: string;
  dpType:
    | 'DEPARTURE'
    | 'ARRIVAL'
    | 'DIRECTION_CHANGE'
    | 'CROSSWALK'
    | 'VERTICAL_MOVE'
    | 'VIRTUAL';
  turnType: number | null;
  location: Location;
  distanceFromStart: number;
  guidance: Guidance;
  selectedLandmark: SelectedLandmark | null;
  panoramaRequest: PanoramaRequest | null;
}

export interface RouteData {
  routeId: string;
  totalDistance: number;
  totalTime: number;
  weather?: any;
  routeLineString: any;
  decisionPoints: DecisionPoint[];
}
