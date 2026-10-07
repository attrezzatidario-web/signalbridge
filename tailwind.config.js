export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'] },
      colors: {
        bg: '#0b0d10', card: '#13161b', line: '#1f242c', mute: '#7d8590',
        up: '#22c55e', down: '#ef4444', accent: '#3b82f6',
      },
    },
  },
  plugins: [],
}
