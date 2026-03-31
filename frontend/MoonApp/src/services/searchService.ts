import { KAKAO_REST_API_KEY } from '../constants/apiKeys';
import type { SearchResult } from '../types/navigation';

const USE_MOCK = true;

const MOCK_RESULTS: SearchResult[] = [
  {
    name: '교보문고 광화문점',
    address: '서울특별시 종로구 종로 1',
    category: '서점',
    lat: 37.5742,
    lng: 126.9902,
  },
  {
    name: '세종문화회관',
    address: '서울특별시 종로구 세종대로 175',
    category: '문화시설',
    lat: 37.5724,
    lng: 126.9760,
  },
  {
    name: '스타벅스 광화문점',
    address: '서울특별시 종로구 세종대로 178',
    category: '카페',
    lat: 37.5718,
    lng: 126.9770,
  },
  {
    name: '국민은행 광화문지점',
    address: '서울특별시 종로구 세종대로 167',
    category: '은행',
    lat: 37.5705,
    lng: 126.9860,
  },
  {
    name: '종각역 1번 출구',
    address: '서울특별시 종로구 종로 지하 55',
    category: '지하철역',
    lat: 37.5700,
    lng: 126.9828,
  },
];

async function searchPlacesMock(query: string): Promise<SearchResult[]> {
  await new Promise<void>((r) => setTimeout(r, 500));
  const lower = query.toLowerCase();
  return MOCK_RESULTS.filter(
    (p) => p.name.includes(lower) || p.address.includes(lower),
  );
}

interface KakaoDocument {
  place_name: string;
  address_name: string;
  category_group_name: string;
  x: string;
  y: string;
}

interface KakaoResponse {
  documents: KakaoDocument[];
}

async function searchPlacesReal(query: string): Promise<SearchResult[]> {
  const url = `https://dapi.kakao.com/v2/local/search/keyword.json?query=${encodeURIComponent(query)}&page=1&size=15`;
  const headers = {
    Authorization: `KakaoAK ${KAKAO_REST_API_KEY}`,
  };

  const response = await fetch(url, { headers });

  if (!response.ok) {
    const rawText = await response.text();
    throw new Error(`Search failed: ${response.status} - ${rawText}`);
  }

  const data: KakaoResponse = await response.json();

  return data.documents.map((doc) => ({
    name: doc.place_name,
    address: doc.address_name,
    category: doc.category_group_name,
    lng: parseFloat(doc.x),
    lat: parseFloat(doc.y),
  }));
}

export async function searchPlaces(query: string): Promise<SearchResult[]> {
  if (USE_MOCK) {
    return searchPlacesMock(query);
  }
  return searchPlacesReal(query);
}
