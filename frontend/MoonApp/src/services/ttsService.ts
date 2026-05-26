import Tts from 'react-native-tts';
import Sound from 'react-native-sound';
import RNFS from 'react-native-fs';
import { BASE_URL } from './routeService';

type GuidanceAudioType = 'primary' | 'preAlert';

interface PrefetchGuidanceAudioItem {
  routeId: string;
  dpId: string;
  type: GuidanceAudioType;
  text?: string | null;
}

// ---------------------------------------------------------------------------
// react-native-tts fallback init
// ---------------------------------------------------------------------------

let initialized = false;

async function init() {
  if (initialized) { return; }
  try {
    const engines = await Tts.engines();
    console.log('[TTS] Available engines:', JSON.stringify(engines));

    await Tts.setDefaultLanguage('ko-KR');
    await Tts.setDefaultRate(0.45);
    await Tts.setDefaultPitch(1.0);
    initialized = true;
    console.log('[TTS] Initialized successfully');
  } catch (e) {
    console.warn('[TTS] init failed:', e);
    initialized = true;
  }
}

// ---------------------------------------------------------------------------
// Audio playback state
// ---------------------------------------------------------------------------

let currentSound: Sound | null = null;
const audioCache = new Map<string, string>();
const inFlightRequests = new Map<string, Promise<string | null>>();

function stopCurrentSound() {
  if (currentSound) {
    currentSound.stop();
    currentSound.release();
    currentSound = null;
  }
}

export function guidanceAudioCacheKey(routeId: string, dpId: string, type: GuidanceAudioType): string {
  return `${routeId}:${dpId}:${type}`;
}

export function getCachedGuidanceAudio(
  routeId: string | null | undefined,
  dpId: string | null | undefined,
  type: GuidanceAudioType,
): string | null {
  if (!routeId || !dpId) { return null; }
  return audioCache.get(guidanceAudioCacheKey(routeId, dpId, type)) ?? null;
}

async function fetchGuidanceAudio(cacheKey: string, text: string): Promise<string | null> {
  const cached = audioCache.get(cacheKey);
  if (cached) { return cached; }

  const inFlight = inFlightRequests.get(cacheKey);
  if (inFlight) { return inFlight; }

  const request = fetch(`${BASE_URL}/tts?text=${encodeURIComponent(text)}`)
    .then(async (res) => {
      if (!res.ok) {
        console.warn('[TTS] remote synth failed:', res.status);
        return null;
      }
      const data = await res.json();
      const audio = data?.audio;
      if (typeof audio === 'string' && audio.length > 0) {
        audioCache.set(cacheKey, audio);
        return audio;
      }
      return null;
    })
    .catch((e) => {
      console.warn('[TTS] remote synth request failed:', e);
      return null;
    })
    .finally(() => {
      inFlightRequests.delete(cacheKey);
    });

  inFlightRequests.set(cacheKey, request);
  return request;
}

export async function prefetchGuidanceAudio(items: PrefetchGuidanceAudioItem[]): Promise<void> {
  const uniqueItems = new Map<string, PrefetchGuidanceAudioItem>();
  for (const item of items) {
    if (!item.routeId || !item.dpId || !item.text) { continue; }
    const cacheKey = guidanceAudioCacheKey(item.routeId, item.dpId, item.type);
    if (audioCache.has(cacheKey)) { continue; }
    uniqueItems.set(cacheKey, item);
  }

  await Promise.all(
    Array.from(uniqueItems.entries()).map(([cacheKey, item]) =>
      fetchGuidanceAudio(cacheKey, item.text as string),
    ),
  );
}

// ---------------------------------------------------------------------------
// Play base64 mp3 audio (Google Cloud TTS)
// ---------------------------------------------------------------------------

async function playBase64Audio(base64Audio: string): Promise<void> {
  stopCurrentSound();

  const filePath = `${RNFS.CachesDirectoryPath}/tts_${Date.now()}.mp3`;

  try {
    await RNFS.writeFile(filePath, base64Audio, 'base64');

    return new Promise<void>((resolve, reject) => {
      const sound = new Sound(filePath, '', (error) => {
        if (error) {
          console.warn('[TTS] Failed to load audio file:', error);
          RNFS.unlink(filePath).catch(() => {});
          reject(error);
          return;
        }
        currentSound = sound;
        sound.play((success) => {
          sound.release();
          currentSound = null;
          RNFS.unlink(filePath).catch(() => {});
          if (success) {
            resolve();
          } else {
            reject(new Error('Playback failed'));
          }
        });
      });
    });
  } catch (e) {
    console.warn('[TTS] playBase64Audio error:', e);
    RNFS.unlink(filePath).catch(() => {});
    throw e;
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Speak guidance text. If base64 mp3 audio is provided (from Google Cloud TTS),
 * play it directly. Otherwise fall back to device TTS (react-native-tts).
 */
export async function speak(text: string, audioBase64?: string | null) {
  console.log('[TTS] speak called:', text.substring(0, 40), audioBase64 ? '(with audio)' : '(device TTS)');

  if (audioBase64) {
    try {
      await playBase64Audio(audioBase64);
      return;
    } catch (e) {
      console.warn('[TTS] Google TTS playback failed, falling back to device TTS:', e);
    }
  }

  // Fallback: device TTS
  await init();
  try {
    Tts.stop();
    Tts.speak(text);
    console.log('[TTS] speaking via device TTS...');
  } catch (e) {
    console.warn('[TTS] speak error:', e);
  }
}

export function stop() {
  stopCurrentSound();
  Tts.stop();
}
