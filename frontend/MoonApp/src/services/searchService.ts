import { KAKAO_REST_API_KEY } from '../constants/apiKeys';
import type { SearchResult } from '../types/navigation';

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

export async function searchPlaces(query: string): Promise<SearchResult[]> {
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
