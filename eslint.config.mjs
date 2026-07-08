import eslint from '@eslint/js';
import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTs from 'eslint-config-next/typescript';
import prettier from 'eslint-config-prettier/flat';
import tseslint from 'typescript-eslint';

// Next.js presets scoped to the web workspace only.
const nextScoped = [...nextVitals, ...nextTs].map((config) => ({
  ...config,
  files: ['apps/web/**/*.{js,jsx,mjs,ts,tsx}'],
  settings: { ...config.settings, next: { rootDir: 'apps/web/' } },
}));

export default tseslint.config(
  {
    ignores: [
      '**/node_modules/',
      '**/dist/',
      '**/.next/',
      '**/coverage/',
      '**/generated/',
      'docs/',
      'tasks/',
    ],
  },
  eslint.configs.recommended,
  tseslint.configs.recommended,
  ...nextScoped,
  prettier,
);
