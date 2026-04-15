import Tts from 'react-native-tts';
import Sound from 'react-native-sound';
import RNFS from 'react-native-fs';

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

function stopCurrentSound() {
  if (currentSound) {
    currentSound.stop();
    currentSound.release();
    currentSound = null;
  }
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
