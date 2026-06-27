module.exports = {
  preset: 'react-native',
  setupFiles: ['./jest.setup.js'],
  testPathIgnorePatterns: ['/node_modules/', '<rootDir>/__tests__/fixtures/'],
  moduleNameMapper: {
    '\\.(png|jpg|jpeg|gif|webp)$': 'react-native/Libraries/Image/RelativeImageStub',
  },
};
