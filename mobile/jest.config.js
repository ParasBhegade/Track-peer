process.env.TZ = 'America/New_York';

const { createDefaultPreset } = require("ts-jest");

const tsJestTransformCfg = createDefaultPreset().transform;

/** @type {import("jest").Config} **/
module.exports = {
  testEnvironment: "node",
  transform: {
    ...tsJestTransformCfg,
  },
  transformIgnorePatterns: [
    "node_modules/(?!(react-native|@react-native|@testing-library|expo|expo-.*|@expo|uuid)/)"
  ],
  moduleNameMapper: {
    "^expo-constants$": "<rootDir>/__mocks__/expo-constants.js"
  }
};