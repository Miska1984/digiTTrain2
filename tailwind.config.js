// tailwind.config.js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./users/templates/**/*.html",
    "./biometric_data/templates/**/*.html",
    // Hozzáadjuk az összes HTML sablonfájlt az alábbiak szerint
    "./core/templates/**/*.html",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}