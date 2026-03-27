import type { RouteData } from '../types/route';
import type { DPItem } from '../types/navigation';

export const MOCK_DP_LIST: DPItem[] = [
  {
    dp_id: 'dp-1',
    lat: 37.5665,
    lng: 126.978,
    turn_type: 12,
    category: 'direction_change',
    description: '스타벅스 광화문점을 지나 우회전하세요',
    landmark_name: '스타벅스 광화문점',
    distance_to_next: 120,
  },
  {
    dp_id: 'dp-2',
    lat: 37.5672,
    lng: 126.9795,
    turn_type: 11,
    category: 'confirmation',
    description: 'GS25 편의점을 지나 계속 직진하세요',
    landmark_name: 'GS25',
    distance_to_next: 200,
  },
  {
    dp_id: 'dp-3',
    lat: 37.569,
    lng: 126.9802,
    turn_type: 211,
    category: 'crosswalk',
    description: '횡단보도를 건넌 후 직진하세요',
    distance_to_next: 80,
  },
  {
    dp_id: 'dp-4',
    lat: 37.5701,
    lng: 126.981,
    turn_type: 13,
    category: 'direction_change',
    description: '투썸플레이스에서 좌회전 후 50m 직진하세요',
    landmark_name: '투썸플레이스',
    distance_to_next: 50,
  },
  {
    dp_id: 'dp-5',
    lat: 37.5708,
    lng: 126.9815,
    turn_type: 201,
    category: 'destination',
    description: '목적지에 도착했습니다',
    distance_to_next: 0,
  },
];

export const MOCK_ROUTE_RESPONSE: RouteData = {
  routeId: 'mock-route-001',
  totalDistance: 1200,
  totalTime: 900,
  routeLineString: {
    type: 'LineString',
    coordinates: [
      [126.978, 37.5665],
      [126.9795, 37.5672],
      [126.9802, 37.569],
      [126.981, 37.5701],
      [126.9815, 37.5708],
    ],
  },
  decisionPoints: [
    {
      dpId: 'dp-1',
      dpType: 'DIRECTION_CHANGE',
      location: { latitude: 37.5665, longitude: 126.978 },
      guideText: '스타벅스 광화문점을 지나 우회전하세요',
      landmarks: [{ name: '스타벅스 광화문점', position: 'RIGHT', category: 'CE7' }],
    },
    {
      dpId: 'dp-2',
      dpType: 'VIRTUAL',
      location: { latitude: 37.5672, longitude: 126.9795 },
      guideText: 'GS25 편의점을 지나 계속 직진하세요',
      landmarks: [{ name: 'GS25', position: 'LEFT', category: 'CS2' }],
    },
    {
      dpId: 'dp-3',
      dpType: 'CROSSWALK',
      location: { latitude: 37.569, longitude: 126.9802 },
      guideText: '횡단보도를 건넌 후 직진하세요',
      landmarks: [],
    },
    {
      dpId: 'dp-4',
      dpType: 'DIRECTION_CHANGE',
      location: { latitude: 37.5701, longitude: 126.981 },
      guideText: '투썸플레이스에서 좌회전 후 50m 직진하세요',
      landmarks: [{ name: '투썸플레이스', position: 'LEFT', category: 'CE7' }],
    },
    {
      dpId: 'dp-5',
      dpType: 'ARRIVAL',
      location: { latitude: 37.5708, longitude: 126.9815 },
      guideText: '목적지에 도착했습니다',
      landmarks: [],
    },
  ],
};
