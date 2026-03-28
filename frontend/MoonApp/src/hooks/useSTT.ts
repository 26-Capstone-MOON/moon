import { useState, useCallback, useRef } from 'react';
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

export function useSTT(): UseSTTReturn {
  const [transcript, setTranscript] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const initialized = useRef(false);

  const initListeners = useCallback(() => {
    if (initialized.current) return;
    initialized.current = true;

    Voice.onSpeechResults = (e: SpeechResultsEvent) => {
      const text = e.value?.[0] ?? '';
      setTranscript(text);
    };

    Voice.onSpeechError = (e: SpeechErrorEvent) => {
      setError(e.error?.message ?? '음성 인식 오류');
      setIsListening(false);
    };

    Voice.onSpeechEnd = () => {
      setIsListening(false);
    };
  }, []);

  const startListening = useCallback(async () => {
    initListeners();
    setError(null);
    setTranscript('');
    try {
      await Voice.start('ko-KR');
      setIsListening(true);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : '음성 인식 시작 실패';
      setError(message);
    }
  }, [initListeners]);

  const stopListening = useCallback(async () => {
    try {
      await Voice.stop();
    } catch {
      // ignore stop errors
    }
    setIsListening(false);
  }, []);

  const reset = useCallback(() => {
    setTranscript('');
    setError(null);
  }, []);

  return { transcript, isListening, error, startListening, stopListening, reset };
}
