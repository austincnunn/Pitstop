// Compiled at Docker build time (see Dockerfile). Primary shades come from
// CSS variables set in base.html from the admin-chosen brand color.
const shades = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900];

module.exports = {
  darkMode: 'class',
  content: ['./app/templates/**/*.html', './app/static/**/*.js', '!./app/static/vendor/**'],
  theme: {
    fontFamily: {
      sans: ['ui-sans-serif', 'system-ui', 'sans-serif', '"Apple Color Emoji"', '"Segoe UI Emoji"', '"Segoe UI Symbol"', '"Noto Color Emoji"'],
    },
    extend: {
      colors: {
        primary: Object.fromEntries(shades.map((n) => [n, `var(--primary-${n})`])),
      },
    },
  },
};
