/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          900: '#0a0a0f',
          800: '#12121a',
          700: '#1a1a26',
          600: '#242436',
          500: '#2d2d42',
          400: '#3d3d55',
          300: '#5a5a75',
          200: '#7a7a95',
          100: '#a0a0b8',
          text: '#c8c8e0',
          muted: '#8888a0',
          accent: '#6c5ce7',
          accentLight: '#a29bfe',
          success: '#00b894',
          warning: '#fdcb6e',
          danger: '#e17055',
          border: '#2a2a3a',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
