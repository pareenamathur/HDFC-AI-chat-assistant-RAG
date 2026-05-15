/** @type {import('tailwindcss').Config} */
/** Tokens aligned with stitch_groww_hdfc_ai_assistant (desktop + DESIGN.md) */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#0D0D0D',
        surface: '#1C1C1E',
        'surface-dim': '#131313',
        'surface-container-lowest': '#0e0e0e',
        'surface-container-low': '#151515',
        'surface-container': '#201f1f',
        'surface-container-high': '#2a2a2a',
        'surface-container-highest': '#353534',
        'on-surface': '#e5e2e1',
        'on-surface-variant': '#A0A0A0',
        'on-background': '#e5e2e1',
        outline: '#2A2A2A',
        'outline-variant': '#3c4a43',
        primary: '#00D09C',
        'on-primary': '#003828',
        'primary-container': '#00d09c',
        'on-primary-container': '#00533c',
        secondary: '#ffb955',
        disclaimer: '#F5A623',
        error: '#ffb4ab',
        'error-container': '#93000a',
      },
      maxWidth: {
        'container-max': '800px',
      },
      spacing: {
        base: '4px',
        gutter: '16px',
      },
      fontSize: {
        'headline-md': ['20px', { lineHeight: '28px', letterSpacing: '-0.01em', fontWeight: '700' }],
        'headline-lg': ['24px', { lineHeight: '32px', letterSpacing: '-0.02em', fontWeight: '700' }],
        'body-md': ['14px', { lineHeight: '20px', fontWeight: '500' }],
        'body-lg': ['16px', { lineHeight: '24px', fontWeight: '400' }],
        'label-sm': ['11px', { lineHeight: '14px', fontWeight: '600' }],
        'label-md': ['12px', { lineHeight: '16px', letterSpacing: '0.01em', fontWeight: '500' }],
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        base: '4px',
      },
    },
  },
  plugins: [],
};
