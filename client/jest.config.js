/**
 * Jest runs the client's unit tests in Node + jsdom — no browser, and fake timers
 * for the services built on them (websocket heartbeats, roll-toast dismissals).
 *
 * `jest-preset-angular` supplies the ts-jest transform (pointed at
 * `tsconfig.spec.json`), the jsdom environment and the Angular snapshot
 * serializers, so only the project-specific bits live here.
 *
 * @type {import('jest').Config}
 */
module.exports = {
  preset: 'jest-preset-angular',
  setupFilesAfterEnv: ['<rootDir>/src/setup-jest.ts'],
  testMatch: ['<rootDir>/src/**/*.spec.ts'],
};
