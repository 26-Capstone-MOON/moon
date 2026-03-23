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
  const response = await fetch(
    `https://dapi.kakao.com/v2/local/search/keyword.json?query=${encodeURIComponent(query)}&page=1&size=15`,
    {
      headers: {
        Authorization: `KakaoAK ${KAKAO_REST_API_KEY}`,
      },
    },
  );

  if (!response.ok) {
    throw new Error(`Search failed: ${response.status}`);
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
