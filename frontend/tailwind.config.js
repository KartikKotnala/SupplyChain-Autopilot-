/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        slate: {
          750: '#233044',
          850: '#141e2e',
        },
        brand: {
          50: '#f0f9ff',
          500: '#0284c7',
          600: '#0369a1',
          700: '#075985',
        }
      }
    },
  },
  plugins: [],
}
