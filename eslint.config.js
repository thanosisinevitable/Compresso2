import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
export default [
 {ignores:['dist/**','release/**','build/**','.venv/**','node_modules/**','.qa/**','.tmp/**','.browsers/**']},
 {files:['**/*.{js,jsx,mjs,cjs}'],languageOptions:{ecmaVersion:'latest',globals:{...globals.browser,...globals.node},parserOptions:{ecmaFeatures:{jsx:true}}},plugins:{'react-hooks':reactHooks,'react-refresh':reactRefresh},rules:{...js.configs.recommended.rules,...reactHooks.configs.recommended.rules,'no-unused-vars':['error',{varsIgnorePattern:'^([A-Z_]|motion$)',argsIgnorePattern:'^[A-Z_]'}]}},
];
