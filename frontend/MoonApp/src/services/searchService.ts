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

  console.log('[SearchService] REQUEST URL:', url);
  console.log('[SearchService] HEADERS:', JSON.stringify(headers));
  console.log('[SearchService] API_KEY:', KAKAO_REST_API_KEY ? `${KAKAO_REST_API_KEY.substring(0, 6)}...` : 'EMPTY!');

  let response: Response;
  try {
    response = await fetch(url, { headers });
  } catch (e) {
    console.error('[SearchService] NETWORK ERROR:', e);
    throw e;
  }

  console.log('[SearchService] STATUS:', response.status, response.statusText);

  const rawText = await response.text();
  console.log('[SearchService] RAW RESPONSE:', rawText.substring(0, 500));

  if (!response.ok) {
    console.error('[SearchService] FAILED:', response.status, rawText);
    throw new Error(`Search failed: ${response.status} - ${rawText}`);
  }

  const data: KakaoResponse = JSON.parse(rawText);
  console.log('[SearchService] RESULTS:', data.documents.length, '건');

  return data.documents.map((doc) => ({
    name: doc.place_name,
    address: doc.address_name,
    category: doc.category_group_name,
    lng: parseFloat(doc.x),
    lat: parseFloat(doc.y),
  }));
}
