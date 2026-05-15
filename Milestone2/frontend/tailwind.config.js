/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#0D1117',
        sidebar: '#0B0F14',
        card: '#111827',
        border: '#1F2937',
        'text-primary': '#E5E7EB',
        'text-secondary': '#9CA3AF',
        accent: '#10B981',
        success: '#22C55E',
        warning: '#F59E0B',
        error: '#F87171',
        'error-bg': '#1A0A0A',
        'warning-bg': '#1A1408',
      },
      maxWidth: {
        chat: '56rem',
      },
      height: {
        header: '4rem',
        sidebar: '16.25rem',
      },
      width: {
        sidebar: '16.25rem',
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        'title-xl': ['1.875rem', { lineHeight: '2.25rem', fontWeight: '700' }],
        'title-lg': ['1.25rem', { lineHeight: '1.75rem', fontWeight: '600' }],
        body: ['0.9375rem', { lineHeight: '1.5rem' }],
        small: ['0.8125rem', { lineHeight: '1.25rem' }],
        xs: ['0.75rem', { lineHeight: '1rem' }],
      },
      boxShadow: {
        card: '0 1px 3px rgba(0,0,0,0.35)',
        glow: '0 0 20px rgba(16, 185, 129, 0.15)',
      },
    },
  },
  plugins: [],
};
