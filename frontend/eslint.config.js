import js from '@eslint/js'
import reactHooks from 'eslint-plugin-react-hooks'
import globals from 'globals'

export default [
  { ignores: ['dist'] },
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: { ...globals.browser, ...globals.node },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { 'react-hooks': reactHooks },
    rules: {
      ...js.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      // JSX identifiers count as used
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]', argsIgnorePattern: '^_' }],
    },
  },
]
