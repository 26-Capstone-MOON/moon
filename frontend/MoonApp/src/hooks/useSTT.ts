import { useState, useCallback, useRef } from 'react';
import { PermissionsAndroid, Platform } from 'react-native';
import Voice, {
  SpeechResultsEvent,
  SpeechErrorEvent,
} from '@react-native-voice/voice';

interface UseSTTReturn {
  transcript: string;
  isListening: boolean;
  error: string | null;
  startListening: () => Promise<void>;
  stopListening: () => Promise<void>;
  reset: () => void;
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
  const initialized = useRef(false);

  const initListeners = useCallback(() => {
    if (initialized.current) { return; }
    initialized.current = true;
    console.log('[STT] initListeners — wiring Voice callbacks');

    Voice.onSpeechStart = () => {
      console.log('[STT] onSpeechStart');
    };

    Voice.onSpeechResults = (e: SpeechResultsEvent) => {
      const text = e.value?.[0] ?? '';
      console.log('[STT] onSpeechResults:', text);
      setTranscript(text);
    };

    Voice.onSpeechPartialResults = (e: SpeechResultsEvent) => {
      const text = e.value?.[0] ?? '';
      console.log('[STT] onSpeechPartialResults:', text);
    };

    Voice.onSpeechError = (e: SpeechErrorEvent) => {
      console.warn('[STT] onSpeechError:', e.error);
      setError(e.error?.message ?? '음성 인식 오류');
      setIsListening(false);
    };

    Voice.onSpeechEnd = () => {
      console.log('[STT] onSpeechEnd');
      setIsListening(false);
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
      const available = await Voice.isAvailable();
      console.log('[STT] Voice.isAvailable:', available);
    } catch (e) {
      console.warn('[STT] Voice.isAvailable check failed:', e);
    }

    try {
      console.log('[STT] calling Voice.start(ko-KR)');
      await Voice.start('ko-KR');
      setIsListening(true);
      console.log('[STT] Voice.start OK — isListening=true');
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : '음성 인식 시작 실패';
      console.error('[STT] Voice.start failed:', message, e);
      setError(message);
    }
  }, [initListeners]);

  const stopListening = useCallback(async () => {
    console.log('[STT] stopListening called');
    try {
      await Voice.stop();
      console.log('[STT] Voice.stop OK');
    } catch (e) {
      console.warn('[STT] Voice.stop error:', e);
    }
    setIsListening(false);
  }, []);

  const reset = useCallback(() => {
    setTranscript('');
    setError(null);
  }, []);

  return { transcript, isListening, error, startListening, stopListening, reset };
}
