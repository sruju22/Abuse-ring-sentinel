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
        background: '#090D16',
        surface: {
          50: '#151C2C',
          100: '#111726',
          200: '#0D121F',
          DEFAULT: '#111726',
          elevated: '#1A233A',
        },
        border: {
          subtle: '#1E293B',
          DEFAULT: '#26334D',
          hover: '#3B4D6E',
        },
        risk: {
          low: '#10B981',
          medium: '#F59E0B',
          high: '#F97316',
          critical: '#EF4444',
        },
        accent: {
          cyan: '#38BDF8',
          indigo: '#818CF8',
          emerald: '#34D399',
          amber: '#FBBF24',
          rose: '#FB7185',
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
