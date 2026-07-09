// Tailwind v4 integrates through PostCSS. Next 16 reads this config under both
// `next dev` (Turbopack) and `next build`; no next.config.ts change is needed.
const config = {
  plugins: {
    '@tailwindcss/postcss': {},
  },
};

export default config;
