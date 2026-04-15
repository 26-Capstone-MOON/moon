import { useCallback, useRef } from 'react';
import { speak, stop } from '../services/ttsService';

interface UseTTSReturn {
  speak: (text: string, audioBase64?: string | null) => Promise<void>;
  stop: () => void;
  isSpeaking: boolean;
}

export function useTTS(): UseTTSReturn {
  const speakingRef = useRef(false);

  const handleSpeak = useCallback(async (text: string, audioBase64?: string | null) => {
    if (!text) return;
    speakingRef.current = true;
    await speak(text, audioBase64);
    speakingRef.current = false;
  }, []);

  const handleStop = useCallback(() => {
    stop();
    speakingRef.current = false;
  }, []);

  return {
    speak: handleSpeak,
    stop: handleStop,
    isSpeaking: speakingRef.current,
  };
}
