import { useState, useEffect, useRef, useCallback } from 'react';
import { Platform, PermissionsAndroid } from 'react-native';
import Geolocation, {
  GeoPosition,
  GeoError,
} from 'react-native-geolocation-service';
import type { GpsPosition } from '../types/location';

interface UseLocationOptions {
  enableHighAccuracy?: boolean;
  interval?: number;
  minAccuracy?: number;
}

interface UseLocationReturn {
  position: GpsPosition | null;
  error: string | null;
  isTracking: boolean;
  startTracking: () => void;
  stopTracking: () => void;
}

const DEFAULT_OPTIONS: Required<UseLocationOptions> = {
  enableHighAccuracy: true,
  interval: 1000,
  minAccuracy: 30,
};

export async function requestLocationPermission(): Promise<boolean> {
  if (Platform.OS === 'android') {
    const granted = await PermissionsAndroid.request(
      PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION,
    );
    return granted === PermissionsAndroid.RESULTS.GRANTED;
  }
  return true;
}

export function useLocation(options?: UseLocationOptions): UseLocationReturn {
  const enableHighAccuracy = options?.enableHighAccuracy ?? DEFAULT_OPTIONS.enableHighAccuracy;
  const interval = options?.interval ?? DEFAULT_OPTIONS.interval;
  const minAccuracy = options?.minAccuracy ?? DEFAULT_OPTIONS.minAccuracy;

  const [position, setPosition] = useState<GpsPosition | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isTracking, setIsTracking] = useState(false);
  const watchId = useRef<number | null>(null);

  const optsRef = useRef({ enableHighAccuracy, interval, minAccuracy });
  optsRef.current = { enableHighAccuracy, interval, minAccuracy };

  const stopTracking = useCallback(() => {
    if (watchId.current !== null) {
      Geolocation.clearWatch(watchId.current);
      watchId.current = null;
    }
    setIsTracking(false);
  }, []);

  const startTracking = useCallback(async () => {
    const hasPermission = await requestLocationPermission();
    if (!hasPermission) {
      setError('현재 위치 권한이 필요합니다. 설정에서 위치 권한을 허용해 주세요.');
      return;
    }

    setError(null);
    setIsTracking(true);

    const opts = optsRef.current;
    watchId.current = Geolocation.watchPosition(
      (pos: GeoPosition) => {
        const { coords } = pos;
        if (coords.accuracy && coords.accuracy > optsRef.current.minAccuracy) {
          return;
        }
        setPosition({
          latitude: coords.latitude,
          longitude: coords.longitude,
          speed: coords.speed,
          heading: coords.heading,
          accuracy: coords.accuracy,
        });
      },
      (err: GeoError) => {
        console.error('[Location] GPS watch failed:', err);
        setError('현재 위치를 확인하지 못했습니다. 잠시 후 다시 시도하세요.');
      },
      {
        enableHighAccuracy: opts.enableHighAccuracy,
        distanceFilter: 0,
        interval: opts.interval,
        fastestInterval: opts.interval,
      },
    );
  }, []);

  useEffect(() => {
    return () => {
      if (watchId.current !== null) {
        Geolocation.clearWatch(watchId.current);
      }
    };
  }, []);

  return { position, error, isTracking, startTracking, stopTracking };
}
