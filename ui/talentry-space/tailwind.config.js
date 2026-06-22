/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: "#000000", 900: "#0a0a0a", 800: "#141414", 700: "#1f1f1f", 600: "#2b2b2b" },
        bone: { 50: "#fafafa", 100: "#f4f4f4", 200: "#e5e5e5", 300: "#cfcfcf", 400: "#9a9a9a" },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
