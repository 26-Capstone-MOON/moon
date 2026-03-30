import type { RouteData } from '../types/route';
import type { DPItem } from '../types/navigation';

export const MOCK_DP_LIST: DPItem[] = [
  {
    dp_id: 'dp-1',
    lat: 37.5696,
    lng: 126.9844,
    turn_type: 12,
    category: 'direction_change',
    description: '오른쪽에 GS25 편의점 보이시죠? 그 앞에서 우회전하세요.',
    landmark_name: 'GS25 광화문점',
    distance_to_next: 150,
  },
  {
    dp_id: 'dp-2',
    lat: 37.5705,
    lng: 126.9860,
    turn_type: 11,
    category: 'confirmation',
    description: '왼쪽에 국민은행 보이면 맞는 길이에요. 계속 직진하세요.',
    landmark_name: '국민은행 광화문지점',
    distance_to_next: 200,
  },
  {
    dp_id: 'dp-3',
    lat: 37.5718,
    lng: 126.9875,
    turn_type: 211,
    category: 'crosswalk',
    description: '올리브영 앞 횡단보도를 건너서, 맞은편 스타벅스 방향으로 직진하세요.',
    landmark_name: '올리브영 종로점',
    distance_to_next: 120,
  },
  {
    dp_id: 'dp-4',
    lat: 37.5728,
    lng: 126.9888,
    turn_type: 127,
    category: 'vertical_move',
    description: '왼쪽 CU 편의점 지나면 바로 계단이 있어요. 계단으로 올라가세요.',
    landmark_name: 'CU 종로3가점',
    distance_to_next: 80,
  },
  {
    dp_id: 'dp-5',
    lat: 37.5735,
    lng: 126.9895,
    turn_type: 13,
    category: 'direction_change',
    description: '전방에 투썸플레이스가 보이면 그 건물 앞에서 좌회전하세요.',
    landmark_name: '투썸플레이스 종로점',
    distance_to_next: 100,
  },
  {
    dp_id: 'dp-6',
    lat: 37.5742,
    lng: 126.9902,
    turn_type: 201,
    category: 'destination',
    description: '오른쪽에 교보문고 건물이 보이면 도착이에요.',
    landmark_name: '교보문고 광화문점',
    distance_to_next: 0,
  },
];

export const MOCK_ROUTE_RESPONSE: RouteData = {
  routeId: 'mock-route-001',
  totalDistance: 1450,
  totalTime: 1080,
  routeLineString: {
    type: 'LineString',
    coordinates: [
      [126.9783, 37.5710],
      [126.9815, 37.5703],
      [126.9844, 37.5696],
      [126.9852, 37.5700],
      [126.9860, 37.5705],
      [126.9868, 37.5712],
      [126.9875, 37.5718],
      [126.9882, 37.5723],
      [126.9888, 37.5728],
      [126.9892, 37.5732],
      [126.9895, 37.5735],
      [126.9902, 37.5742],
    ],
  },
  decisionPoints: [
    {
      dpId: 'dp-0',
      dpType: 'DEPARTURE',
      location: { latitude: 37.5710, longitude: 126.9783 },
      guideText: '세종대로 사거리에서 출발합니다. 종로 방면으로 직진하세요.',
      landmarks: [],
    },
    {
      dpId: 'dp-1',
      dpType: 'DIRECTION_CHANGE',
      location: { latitude: 37.5696, longitude: 126.9844 },
      guideText: '오른쪽에 GS25 편의점 보이시죠? 그 앞에서 우회전하세요.',
      landmarks: [
        { name: 'GS25 광화문점', position: 'RIGHT', category: 'CS2' },
      ],
    },
    {
      dpId: 'dp-2',
      dpType: 'VIRTUAL',
      location: { latitude: 37.5705, longitude: 126.9860 },
      guideText: '왼쪽에 국민은행 보이면 맞는 길이에요. 계속 직진하세요.',
      landmarks: [
        { name: '국민은행 광화문지점', position: 'LEFT', category: 'BK9' },
      ],
    },
    {
      dpId: 'dp-3',
      dpType: 'CROSSWALK',
      location: { latitude: 37.5718, longitude: 126.9875 },
      guideText: '올리브영 앞 횡단보도를 건너서, 맞은편 스타벅스 방향으로 직진하세요.',
      landmarks: [
        { name: '올리브영 종로점', position: 'RIGHT', category: 'CS2' },
      ],
    },
    {
      dpId: 'dp-4',
      dpType: 'VERTICAL_MOVE',
      location: { latitude: 37.5728, longitude: 126.9888 },
      guideText: '왼쪽 CU 편의점 지나면 바로 계단이 있어요. 계단으로 올라가세요.',
      landmarks: [
        { name: 'CU 종로3가점', position: 'LEFT', category: 'CS2' },
      ],
    },
    {
      dpId: 'dp-5',
      dpType: 'DIRECTION_CHANGE',
      location: { latitude: 37.5735, longitude: 126.9895 },
      guideText: '전방에 투썸플레이스가 보이면 그 건물 앞에서 좌회전하세요.',
      landmarks: [
        { name: '투썸플레이스 종로점', position: 'FRONT', category: 'CE7' },
      ],
    },
    {
      dpId: 'dp-6',
      dpType: 'ARRIVAL',
      location: { latitude: 37.5742, longitude: 126.9902 },
      guideText: '오른쪽에 교보문고 건물이 보이면 도착이에요.',
      landmarks: [
        { name: '교보문고 광화문점', position: 'RIGHT', category: 'SW8' },
      ],
    },
  ],
};
