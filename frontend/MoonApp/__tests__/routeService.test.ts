import { fetchRoute } from '../src/services/routeService';
import type { Place } from '../src/types/navigation';

const origin: Place = {
  name: 'Origin',
  address: 'Origin address',
  lat: 37.5,
  lng: 127.0,
};

const destination: Place = {
  name: 'Destination',
  address: 'Destination address',
  lat: 37.6,
  lng: 127.1,
};

describe('routeService failure behavior', () => {
  const originalFetch = globalThis.fetch;
  let consoleErrorSpy: jest.SpyInstance;

  beforeEach(() => {
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    consoleErrorSpy.mockRestore();
    jest.clearAllMocks();
  });

  it('throws the route error instead of returning a mock route on network failure', async () => {
    globalThis.fetch = jest.fn().mockRejectedValue(new Error('network down')) as unknown as typeof fetch;

    await expect(fetchRoute(origin, destination)).rejects.toThrow(
      '경로를 불러오지 못했습니다. 네트워크 연결 또는 서버 상태를 확인한 뒤 다시 시도하세요.',
    );
  });

  it('throws the route error instead of returning a mock route on HTTP failure', async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
    }) as unknown as typeof fetch;

    await expect(fetchRoute(origin, destination)).rejects.toThrow(
      '경로를 불러오지 못했습니다. 네트워크 연결 또는 서버 상태를 확인한 뒤 다시 시도하세요.',
    );
  });
});
