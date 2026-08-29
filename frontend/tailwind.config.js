/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#070e1c',
          raised: '#0c1425',
          card: '#0f172a',
          hover: '#141e33',
          active: '#1a2740',
          border: '#1c2536',
          'border-subtle': '#151d2e',
        },
        text: {
          primary: '#f4f5f7',
          secondary: '#97a0af',
          tertiary: '#5e6c84',
          inverse: '#070e1c',
        },
        accent: {
          DEFAULT: '#0d94fb',
          hover: '#3aabfc',
          muted: 'rgba(13,148,251,0.10)',
          deep: '#012652',
        },
        status: {
          success: '#04db7c',
          'success-muted': 'rgba(4,219,124,0.10)',
          warning: '#f5a623',
          'warning-muted': 'rgba(245,166,35,0.10)',
          danger: '#ff4d4f',
          'danger-muted': 'rgba(255,77,79,0.10)',
          info: '#0d94fb',
          'info-muted': 'rgba(13,148,251,0.10)',
        },
        grade: {
          a: '#04db7c',
          b: '#52c41a',
          c: '#f5a623',
          d: '#fa8c16',
          f: '#ff4d4f',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        display: ['3rem', { lineHeight: '1.1', letterSpacing: '-0.03em', fontWeight: '700' }],
        h1: ['2.25rem', { lineHeight: '1.2', letterSpacing: '-0.02em', fontWeight: '700' }],
        h2: ['1.5rem', { lineHeight: '1.3', letterSpacing: '-0.01em', fontWeight: '600' }],
        h3: ['1.125rem', { lineHeight: '1.4', letterSpacing: '-0.01em', fontWeight: '600' }],
        body: ['0.875rem', { lineHeight: '1.6', fontWeight: '400' }],
        'body-sm': ['0.8125rem', { lineHeight: '1.5', fontWeight: '400' }],
        caption: ['0.75rem', { lineHeight: '1.5', fontWeight: '500' }],
        overline: ['0.6875rem', { lineHeight: '1.4', fontWeight: '600', letterSpacing: '0.08em' }],
      },
      borderRadius: {
        sm: '4px',
        DEFAULT: '6px',
        md: '8px',
        lg: '12px',
        xl: '16px',
      },
      boxShadow: {
        low: '0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)',
        mid: '0 4px 12px rgba(0,0,0,0.4), 0 2px 4px rgba(0,0,0,0.3)',
        high: '0 12px 40px rgba(0,0,0,0.5), 0 4px 12px rgba(0,0,0,0.3)',
        'glow-accent': '0 0 20px rgba(13,148,251,0.15)',
        'glow-success': '0 0 20px rgba(4,219,124,0.15)',
        'glow-danger': '0 0 20px rgba(255,77,79,0.15)',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'slide-in-right': 'slideInRight 0.3s ease-out',
        shimmer: 'shimmer 2s infinite linear',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideInRight: {
          '0%': { opacity: '0', transform: 'translateX(16px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
    },
  },
  plugins: [],
}
