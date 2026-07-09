// Vitest setup: schema tests compile schemas directly (TypeCompiler/Value), so the
// string formats must be registered before any test file runs.
import { registerFormats } from '../formats.js';

registerFormats();
