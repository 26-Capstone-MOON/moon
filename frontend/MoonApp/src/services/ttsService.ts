import Tts from 'react-native-tts';

let initialized = false;

async function init() {
  if (initialized) { return; }
  try {
    await Tts.setDefaultLanguage('ko-KR');
    await Tts.setDefaultRate(0.45);
    await Tts.setDefaultPitch(1.0);
    initialized = true;
  } catch (e) {
    console.warn('TTS init failed:', e);
  }
}

export async function speak(text: string) {
  await init();
  Tts.stop();
  Tts.speak(text);
}

export function stop() {
  Tts.stop();
}
