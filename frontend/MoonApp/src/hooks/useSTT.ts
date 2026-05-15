import { useCallback, useEffect, useRef, useState } from 'react';
import {
  EmitterSubscription,
  NativeEventEmitter,
  NativeModules,
  PermissionsAndroid,
  Platform,
} from 'react-native';

interface UseSTTReturn {
  transcript: string;
  isListening: boolean;
  error: string | null;
  startListening: () => Promise<void>;
  stopListening: () => Promise<void>;
  reset: () => void;
}

interface SpeechResultsEvent {
  value?: string[];
}

interface SpeechErrorEvent {
  error?: { message?: string; code?: string };
}

const RCTVoice = (NativeModules as Record<string, any>).RCTVoice;

function startSpeechNative(locale: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!RCTVoice) {
      reject(new Error('RCTVoice native module not available'));
      return;
    }
    RCTVoice.startSpeech(
      locale,
      {
        EXTRA_LANGUAGE_MODEL: 'LANGUAGE_MODEL_FREE_FORM',
        EXTRA_MAX_RESULTS: 5,
        EXTRA_PARTIAL_RESULTS: true,
        REQUEST_PERMISSIONS_AUTO: true,
      },
      (err: string | null) => {
        if (err) { reject(new Error(err)); } else { resolve(); }
      },
    );
  });
}

function stopSpeechNative(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!RCTVoice) { resolve(); return; }
    RCTVoice.stopSpeech((err: string | null) => {
      if (err) { reject(new Error(err)); } else { resolve(); }
    });
  });
}

function isSpeechAvailableNative(): Promise<boolean> {
  return new Promise((resolve) => {
    if (!RCTVoice) { resolve(false); return; }
    RCTVoice.isSpeechAvailable((available: 0 | 1) => {
      resolve(!!available);
    });
  });
}

async function ensureMicPermission(): Promise<boolean> {
  if (Platform.OS !== 'android') {
    return true;
  }
  try {
    const already = await PermissionsAndroid.check(
      PermissionsAndroid.PERMISSIONS.RECORD_AUDIO,
    );
    console.log('[STT] permission check:', already);
    if (already) { return true; }

    const granted = await PermissionsAndroid.request(
      PermissionsAndroid.PERMISSIONS.RECORD_AUDIO,
      {
        title: '마이크 권한 요청',
        message: '음성으로 질문하려면 마이크 권한이 필요합니다.',
        buttonPositive: '허용',
        buttonNegative: '취소',
      },
    );
    console.log('[STT] permission request result:', granted);
    return granted === PermissionsAndroid.RESULTS.GRANTED;
  } catch (e) {
    console.warn('[STT] permission request error:', e);
    return false;
  }
}

export function useSTT(): UseSTTReturn {
  const [transcript, setTranscript] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const subsRef = useRef<EmitterSubscription[]>([]);
  const initialized = useRef(false);

  const initListeners = useCallback(() => {
    if (initialized.current) { return; }
    if (!RCTVoice) {
      console.warn('[STT] RCTVoice native module not available — listeners not wired');
      return;
    }
    initialized.current = true;
    console.log('[STT] initListeners — wiring RCTVoice events');

    const emitter = new NativeEventEmitter(RCTVoice);
    subsRef.current.push(
      emitter.addListener('onSpeechStart', () => {
        console.log('[STT] onSpeechStart');
      }),
      emitter.addListener('onSpeechResults', (e: SpeechResultsEvent) => {
        const text = e.value?.[0] ?? '';
        console.log('[STT] onSpeechResults:', text);
        setTranscript(text);
      }),
      emitter.addListener('onSpeechPartialResults', (e: SpeechResultsEvent) => {
        const text = e.value?.[0] ?? '';
        console.log('[STT] onSpeechPartialResults:', text);
      }),
      emitter.addListener('onSpeechError', (e: SpeechErrorEvent) => {
        console.warn('[STT] onSpeechError:', e.error);
        setError(e.error?.message ?? '음성 인식 오류');
        setIsListening(false);
      }),
      emitter.addListener('onSpeechEnd', () => {
        console.log('[STT] onSpeechEnd');
        setIsListening(false);
      }),
    );
  }, []);

  useEffect(() => {
    return () => {
      subsRef.current.forEach((s) => s.remove());
      subsRef.current = [];
      initialized.current = false;
    };
  }, []);

  const startListening = useCallback(async () => {
    console.log('[STT] startListening called');
    initListeners();
    setError(null);
    setTranscript('');

    const hasPermission = await ensureMicPermission();
    if (!hasPermission) {
      console.warn('[STT] mic permission denied');
      setError('마이크 권한이 필요합니다');
      return;
    }

    try {
      const available = await isSpeechAvailableNative();
      console.log('[STT] isSpeechAvailable:', available);
    } catch (e) {
      console.warn('[STT] isSpeechAvailable check failed:', e);
    }

    try {
      console.log('[STT] calling startSpeech(ko-KR)');
      await startSpeechNative('ko-KR');
      setIsListening(true);
      console.log('[STT] startSpeech OK — isListening=true');
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : '음성 인식 시작 실패';
      console.error('[STT] startSpeech failed:', message, e);
      setError(message);
    }
  }, [initListeners]);

  const stopListening = useCallback(async () => {
    console.log('[STT] stopListening called');
    try {
      await stopSpeechNative();
      console.log('[STT] stopSpeech OK');
    } catch (e) {
      console.warn('[STT] stopSpeech error:', e);
    }
    setIsListening(false);
  }, []);

  const reset = useCallback(() => {
    setTranscript('');
    setError(null);
  }, []);

  return { transcript, isListening, error, startListening, stopListening, reset };
}
