// -----------------------------------------------------------------------------
// frontend/.eslintrc.cjs
//
// ESLint v8 flat-style legacy config for the frontend, referenced by the
// `lint` script in package.json. Extends the recommended rule sets for
// plain JS, React, and react-hooks; disables react/prop-types (no
// PropTypes used in this codebase) and react/react-in-jsx-scope (not
// needed with the React 18 JSX transform).
// -----------------------------------------------------------------------------

module.exports = {
  env: {
    browser: true,
    es2021: true,
  },
  extends: ['eslint:recommended', 'plugin:react/recommended', 'plugin:react-hooks/recommended'],
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    ecmaFeatures: {
      jsx: true,
    },
  },
  plugins: ['react', 'react-hooks'],
  rules: {
    'react/prop-types': 'off',
    'react/react-in-jsx-scope': 'off',
  },
  settings: {
    react: {
      version: 'detect',
    },
  },
}
