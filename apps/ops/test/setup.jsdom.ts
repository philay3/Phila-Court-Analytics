// jsdom test setup (task 12.2). Loaded only by the `jsdom` Vitest project, so
// the node-environment suites never pull in DOM matchers. Registers the
// @testing-library/jest-dom matchers on Vitest's `expect` and unmounts any
// rendered tree after each test to keep component tests isolated.
import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => {
  cleanup();
});
