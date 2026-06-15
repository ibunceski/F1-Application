/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        f1: {
          red: '#E8002D',
          dark: '#0A0A0A',
          surface: '#111118',
          elevated: '#1A1A27',
          border: '#2A2A3D',
          muted: '#6B6B80',
          text: '#E8E8F0',
          white: '#FFFFFF',
        },
        compound: {
          soft: '#FF1421',
          medium: '#FFF000',
          hard: '#EBEBEB',
          inter: '#48C774',
          wet: '#1E90FF',
        },
        podium: {
          gold: '#FFD700',
          silver: '#C0C0C0',
          bronze: '#CD7F32',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        display: ['Inter', 'sans-serif'],
      },
      fontSize: {
        data: ['0.75rem', { lineHeight: '1rem', letterSpacing: '0.05em' }],
      },
    },
  },
  plugins: [],
};
