import Tts from 'react-native-tts';

let initialized = false;

async function init() {
  if (initialized) { return; }
  try {
    // Check available engines first
    const engines = await Tts.engines();
    console.log('[TTS] Available engines:', JSON.stringify(engines));

    await Tts.setDefaultLanguage('ko-KR');
    await Tts.setDefaultRate(0.45);
    await Tts.setDefaultPitch(1.0);
    initialized = true;
    console.log('[TTS] Initialized successfully');
  } catch (e) {
    console.warn('[TTS] init failed:', e);
    // Retry without language setting
    try {
      initialized = true;
      console.log('[TTS] Initialized without language setting');
    } catch (e2) {
      console.warn('[TTS] fallback init also failed:', e2);
    }
  }
}

export async function speak(text: string) {
  console.log('[TTS] speak called:', text);
  await init();
  try {
    Tts.stop();
    Tts.speak(text);
    console.log('[TTS] speaking...');
  } catch (e) {
    console.warn('[TTS] speak error:', e);
  }
}

export function stop() {
  Tts.stop();
}
