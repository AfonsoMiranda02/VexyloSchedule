/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./website/templates/**/*.html",
    "./static/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#722F37',
        primaryHover: '#5A252C',
        bgSoft: '#FAF9F6',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        heading: ['Outfit', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
