/* eslint-env jest */
import 'react-native-gesture-handler/jestSetup';

jest.mock(
  '@react-native-async-storage/async-storage',
  () => ({
    getItem: jest.fn(() => Promise.resolve(null)),
    setItem: jest.fn(() => Promise.resolve()),
    removeItem: jest.fn(() => Promise.resolve()),
    clear: jest.fn(() => Promise.resolve()),
  }),
);

jest.mock('react-native-vector-icons/Ionicons', () => 'Icon');

jest.mock('@mj-studio/react-native-naver-map', () => {
  const React = require('react');
  const { View } = require('react-native');
  const Stub = ({ children }) => React.createElement(View, null, children);
  return {
    NaverMapView: Stub,
    NaverMapMarkerOverlay: Stub,
    NaverMapPathOverlay: Stub,
  };
});

jest.mock('react-native-geolocation-service', () => ({
  watchPosition: jest.fn(() => 1),
  clearWatch: jest.fn(),
}));

jest.mock('react-native-webview', () => 'WebView');

jest.mock('react-native-tts', () => ({
  setDefaultLanguage: jest.fn(),
  setDefaultRate: jest.fn(),
  setDefaultPitch: jest.fn(),
  speak: jest.fn(),
  stop: jest.fn(),
  addEventListener: jest.fn(() => ({ remove: jest.fn() })),
}));

jest.mock('react-native-sound', () => {
  const Sound = jest.fn().mockImplementation(() => ({
    play: jest.fn((callback) => callback?.(true)),
    stop: jest.fn(),
    release: jest.fn(),
  }));
  Sound.setCategory = jest.fn();
  return Sound;
});

jest.mock('react-native-fs', () => ({
  CachesDirectoryPath: '/tmp',
  exists: jest.fn(() => Promise.resolve(false)),
  mkdir: jest.fn(() => Promise.resolve()),
  stat: jest.fn(() => Promise.resolve({ size: 2048 })),
  hash: jest.fn(() => Promise.resolve('test-sha256')),
  writeFile: jest.fn(() => Promise.resolve()),
  readFile: jest.fn(() => Promise.resolve('')),
  unlink: jest.fn(() => Promise.resolve()),
}));

jest.mock('@gorhom/bottom-sheet', () => {
  const React = require('react');
  const { View } = require('react-native');
  const Stub = React.forwardRef(({ children }, ref) => React.createElement(View, { ref }, children));
  return {
    __esModule: true,
    default: Stub,
    BottomSheetScrollView: Stub,
  };
});

jest.mock('react-native-reanimated', () => {
  const { View } = require('react-native');
  return {
    __esModule: true,
    default: {
      View,
      createAnimatedComponent: (Component) => Component,
    },
    View,
    createAnimatedComponent: (Component) => Component,
    useAnimatedStyle: jest.fn(() => ({})),
    useSharedValue: jest.fn((value) => ({ value })),
    withTiming: jest.fn((value) => value),
    interpolate: jest.fn(() => 0),
    Extrapolation: { CLAMP: 'clamp' },
  };
});
