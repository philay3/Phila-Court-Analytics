import eslint from '@eslint/js';
import prettier from 'eslint-config-prettier/flat';
import tseslint from 'typescript-eslint';

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
  prettier,
);
