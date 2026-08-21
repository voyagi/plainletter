// Complexity, cognitive complexity and cross-browser compat floors, merged with the framework
// config. The thresholds are deliberately high: a floor that fires only on genuinely tangled
// functions, never a style nag. A hit means refactor the hotspot or raise it for that one file with
// a written reason, never a blanket disable.
import coreWebVitals from 'eslint-config-next/core-web-vitals';
import nextTypescript from 'eslint-config-next/typescript';
import compat from 'eslint-plugin-compat';
import sonarjs from 'eslint-plugin-sonarjs';
import tseslint from 'typescript-eslint';

const tsParser = { parser: tseslint.parser, parserOptions: { ecmaVersion: 'latest', sourceType: 'module' } };

const config = [
  // dependency-cruiser loads its own config as CommonJS, so that one file cannot be ESM and is not
  // linted as if it were.
  { ignores: ['.next/**', 'node_modules/**', 'coverage/**', 'next-env.d.ts', '.dependency-cruiser.cjs'] },
  ...coreWebVitals,
  ...nextTypescript,
  {
    files: ['**/*.{ts,tsx,mjs}'],
    ignores: ['**/*.{test,spec}.{ts,tsx}', '**/*.config.{ts,mjs}'],
    languageOptions: { ...tsParser },
    plugins: { sonarjs },
    rules: {
      complexity: ['error', 25],
      'sonarjs/cognitive-complexity': ['error', 25],
    },
  },
  // Browser code only. On server modules this rule false-positives on Node-valid syntax, so
  // src/server is excluded rather than the globs widened.
  {
    files: ['src/app/**/*.tsx', 'src/components/**/*.{ts,tsx}'],
    ignores: ['src/server/**'],
    languageOptions: { ...tsParser },
    plugins: { compat },
    rules: { 'compat/compat': 'error' },
  },
];

export default config;
