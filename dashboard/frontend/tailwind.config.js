/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: '#F3F1EB',
        surface: {
          50: '#FFFFFF',
          100: '#FFFFFF',
          200: '#FFFFFF',
          DEFAULT: '#FFFFFF',
          elevated: '#F7F6F2',
        },
        border: {
          subtle: '#E2E0D8',
          DEFAULT: '#E2E0D8',
          hover: '#C8C5BC',
        },
        risk: {
          low: '#147D69',
          medium: '#B99A45',
          high: '#D58A27',
          critical: '#C64B43',
        },
        accent: {
          cyan: '#147D69',
          indigo: '#7C6EAF',
          emerald: '#147D69',
          amber: '#D58A27',
          rose: '#C64B43',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Menlo', 'monospace'],
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
