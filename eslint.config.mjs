// Flat config. One rule set for every workspace — a per-workspace config is how
// a rule quietly stops applying to the directory that needed it most.
import js from '@eslint/js';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  {
    // Build output, vendored trees, and the Python sidecar. `resources/` is
    // gitignored working documents; `aligner/` is Python with a JSON artifact
    // directory that is evidence, not source.
    ignores: [
      '**/node_modules/**',
      '**/dist/**',
      '**/build/**',
      '**/.next/**',
      '**/.expo/**',
      '**/coverage/**',
      'resources/**',
      // Session scratch; gitignored, not source.
      '.remember/**',
      'aligner/**',
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: 'module',
      globals: { ...globals.node },
    },
    rules: {
      // The gate tool and the secret scanner are deliberately console-driven:
      // their output IS the product.
      'no-console': 'off',
      eqeqeq: ['error', 'always', { null: 'ignore' }],
      'no-var': 'error',
      'prefer-const': 'error',
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      // An empty catch is how a failure becomes silence, which is the defect
      // class this repository has spent twenty-seven audits on.
      'no-empty': ['error', { allowEmptyCatch: false }],
    },
  },
  {
    // tools/ and .github/scripts/ are plain ESM run by node directly.
    files: ['tools/**/*.mjs', '.github/scripts/**/*.mjs'],
    languageOptions: { sourceType: 'module' },
  },
);
