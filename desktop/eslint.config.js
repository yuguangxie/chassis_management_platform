import js from '@eslint/js'
import vue from 'eslint-plugin-vue'
import tseslint from 'typescript-eslint'

export default [
  { ignores: ['dist/**', 'coverage/**', 'node_modules/**', 'electron/**/*.cjs'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  // Vue must be applied after the TypeScript preset so .vue templates retain
  // vue-eslint-parser instead of being parsed as plain TypeScript.
  ...vue.configs['flat/recommended'],
  {
    files: ['**/*.vue'],
    languageOptions: {
      parserOptions: {
        parser: tseslint.parser,
        extraFileExtensions: ['.vue'],
      },
    },
  },
  {
    files: ['src/**/*.{ts,vue}'],
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
      // The existing dashboard pages intentionally co-locate tiny render helpers
      // and legacy imports. Keep this baseline lint non-disruptive while tests
      // and typecheck enforce executable paths; tighten it incrementally later.
      '@typescript-eslint/no-unused-vars': 'off',
      'vue/multi-word-component-names': 'off',
      'vue/max-attributes-per-line': 'off',
      'vue/singleline-html-element-content-newline': 'off',
      'vue/html-self-closing': 'off',
      'vue/one-component-per-file': 'off',
      'vue/attributes-order': 'off',
      'vue/multiline-html-element-content-newline': 'off',
      'vue/html-indent': 'off',
      'no-irregular-whitespace': 'off',
      'no-extra-boolean-cast': 'off',
    },
  },
]
